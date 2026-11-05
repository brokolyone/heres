//! Поиск и замена в UTF-16 тексте. Позиции — в UTF-16 единицах, как у EDIT-контрола.

#[derive(Clone, Copy, Debug, Default)]
pub struct Options {
    pub match_case: bool,
    pub whole_word: bool,
    /// Искать вверх (к началу текста).
    pub up: bool,
    /// Продолжать с другого конца, если дошли до края.
    pub wrap: bool,
}

/// Сравнение без учёта регистра для символов BMP (суррогаты сравниваются как есть).
fn fold(u: u16) -> u16 {
    match char::from_u32(u as u32) {
        Some(c) => {
            let mut l = c.to_lowercase();
            match (l.next(), l.next()) {
                (Some(x), None) if (x as u32) <= 0xFFFF => x as u16,
                _ => u,
            }
        }
        None => u,
    }
}

fn is_word(u: u16) -> bool {
    char::from_u32(u as u32).is_some_and(|c| c.is_alphanumeric() || c == '_')
}

fn matches_at(hay: &[u16], needle: &[u16], at: usize, o: &Options) -> bool {
    if at + needle.len() > hay.len() {
        return false;
    }
    let same = hay[at..at + needle.len()]
        .iter()
        .zip(needle)
        .all(|(&a, &b)| a == b || (!o.match_case && fold(a) == fold(b)));
    if !same {
        return false;
    }
    if o.whole_word {
        let before = at.checked_sub(1).map(|i| hay[i]);
        let after = hay.get(at + needle.len()).copied();
        if before.is_some_and(is_word) || after.is_some_and(is_word) {
            return false;
        }
    }
    true
}

/// Ищет `needle`. Вниз — начиная с `from` включительно; вверх — совпадение,
/// которое начинается строго до `from`. Возвращает позицию начала.
pub fn find(hay: &[u16], needle: &[u16], from: usize, o: &Options) -> Option<usize> {
    if needle.is_empty() || needle.len() > hay.len() {
        return None;
    }
    let last = hay.len() - needle.len();
    let from = from.min(hay.len());
    if o.up {
        let below = (0..from.min(last + 1)).rev().find(|&i| matches_at(hay, needle, i, o));
        below.or_else(|| {
            o.wrap.then(|| (from..=last).rev().find(|&i| matches_at(hay, needle, i, o))).flatten()
        })
    } else {
        let after = (from..=last).find(|&i| matches_at(hay, needle, i, o));
        after.or_else(|| o.wrap.then(|| (0..from.min(last + 1)).find(|&i| matches_at(hay, needle, i, o))).flatten())
    }
}

/// Заменяет все вхождения. Возвращает новый текст и число замен.
pub fn replace_all(hay: &[u16], needle: &[u16], with: &[u16], o: &Options) -> (Vec<u16>, usize) {
    if needle.is_empty() {
        return (hay.to_vec(), 0);
    }
    let mut out = Vec::with_capacity(hay.len());
    let (mut i, mut n) = (0, 0);
    while i < hay.len() {
        if matches_at(hay, needle, i, o) {
            out.extend_from_slice(with);
            i += needle.len();
            n += 1;
        } else {
            out.push(hay[i]);
            i += 1;
        }
    }
    (out, n)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn u(s: &str) -> Vec<u16> {
        s.encode_utf16().collect()
    }

    #[test]
    fn down_and_up() {
        let h = u("кот и Кот и КОТ");
        let o = Options::default();
        assert_eq!(find(&h, &u("кот"), 0, &o), Some(0));
        assert_eq!(find(&h, &u("кот"), 1, &o), Some(6));
        assert_eq!(find(&h, &u("кот"), 7, &o), Some(12));
        assert_eq!(find(&h, &u("кот"), 13, &o), None);
        let up = Options { up: true, ..o };
        assert_eq!(find(&h, &u("кот"), 12, &up), Some(6));
        assert_eq!(find(&h, &u("кот"), 0, &up), None);
    }

    #[test]
    fn case_and_wrap() {
        let h = u("кот и Кот");
        let cs = Options { match_case: true, ..Default::default() };
        assert_eq!(find(&h, &u("Кот"), 0, &cs), Some(6));
        let wrap = Options { wrap: true, ..Default::default() };
        assert_eq!(find(&h, &u("кот"), 7, &wrap), Some(0));
        let wrap_up = Options { wrap: true, up: true, ..Default::default() };
        assert_eq!(find(&h, &u("кот"), 0, &wrap_up), Some(6));
    }

    #[test]
    fn whole_word() {
        let h = u("котик кот");
        let o = Options { whole_word: true, ..Default::default() };
        assert_eq!(find(&h, &u("кот"), 0, &o), Some(6));
    }

    #[test]
    fn replace() {
        let (r, n) = replace_all(&u("a-A-a"), &u("a"), &u("бб"), &Options::default());
        assert_eq!((r, n), (u("бб-бб-бб"), 3));
        let (r, n) = replace_all(&u("a-A"), &u("a"), &u("x"), &Options { match_case: true, ..Default::default() });
        assert_eq!((r, n), (u("x-A"), 1));
    }
}
