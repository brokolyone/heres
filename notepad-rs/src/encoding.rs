//! Определение кодировки и концов строк, перевод в формат EDIT-контрола и обратно.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Encoding {
    Utf8,
    Utf8Bom,
    Utf16Le,
    Utf16Be,
    /// Системная однобайтовая кодировка (CP_ACP, у нас обычно Windows-1251).
    Ansi,
}

impl Encoding {
    pub fn label(self) -> &'static str {
        match self {
            Encoding::Utf8 => "UTF-8",
            Encoding::Utf8Bom => "UTF-8 с BOM",
            Encoding::Utf16Le => "UTF-16 LE",
            Encoding::Utf16Be => "UTF-16 BE",
            Encoding::Ansi => "ANSI",
        }
    }

    pub const ALL: [Encoding; 5] = [
        Encoding::Utf8,
        Encoding::Utf8Bom,
        Encoding::Utf16Le,
        Encoding::Utf16Be,
        Encoding::Ansi,
    ];
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Eol {
    CrLf,
    Lf,
    Cr,
}

impl Eol {
    pub fn label(self) -> &'static str {
        match self {
            Eol::CrLf => "Windows (CRLF)",
            Eol::Lf => "Unix (LF)",
            Eol::Cr => "Macintosh (CR)",
        }
    }
}

/// Результат чтения файла: текст для EDIT-контрола (всегда CRLF) и исходный формат.
#[derive(Debug, PartialEq, Eq)]
pub struct Decoded {
    pub text: Vec<u16>,
    pub encoding: Encoding,
    pub eol: Eol,
}

/// Читает байты файла. `ansi` переводит байты из системной кодировки в UTF-16
/// (под Windows — через MultiByteToWideChar).
pub fn decode(bytes: &[u8], ansi: impl Fn(&[u8]) -> Vec<u16>) -> Decoded {
    let (units, encoding): (Vec<u16>, Encoding) = if let Some(rest) = bytes.strip_prefix(&[0xEF, 0xBB, 0xBF]) {
        (String::from_utf8_lossy(rest).encode_utf16().collect(), Encoding::Utf8Bom)
    } else if let Some(rest) = bytes.strip_prefix(&[0xFF, 0xFE]) {
        (utf16_from_bytes(rest, u16::from_le_bytes), Encoding::Utf16Le)
    } else if let Some(rest) = bytes.strip_prefix(&[0xFE, 0xFF]) {
        (utf16_from_bytes(rest, u16::from_be_bytes), Encoding::Utf16Be)
    } else if let Ok(s) = std::str::from_utf8(bytes) {
        (s.encode_utf16().collect(), Encoding::Utf8)
    } else {
        (ansi(bytes), Encoding::Ansi)
    };
    let eol = detect_eol(&units);
    Decoded { text: to_crlf(&units), encoding, eol }
}

/// Сохраняет текст из EDIT-контрола (CRLF) в нужном формате.
/// `ansi` переводит UTF-16 в системную кодировку.
pub fn encode(text: &[u16], encoding: Encoding, eol: Eol, ansi: impl Fn(&[u16]) -> Vec<u8>) -> Vec<u8> {
    let units = from_crlf(text, eol);
    match encoding {
        Encoding::Utf8 => String::from_utf16_lossy(&units).into_bytes(),
        Encoding::Utf8Bom => {
            let mut out = vec![0xEF, 0xBB, 0xBF];
            out.extend_from_slice(String::from_utf16_lossy(&units).as_bytes());
            out
        }
        Encoding::Utf16Le => {
            let mut out = vec![0xFF, 0xFE];
            units.iter().for_each(|u| out.extend_from_slice(&u.to_le_bytes()));
            out
        }
        Encoding::Utf16Be => {
            let mut out = vec![0xFE, 0xFF];
            units.iter().for_each(|u| out.extend_from_slice(&u.to_be_bytes()));
            out
        }
        Encoding::Ansi => ansi(&units),
    }
}

fn utf16_from_bytes(bytes: &[u8], f: fn([u8; 2]) -> u16) -> Vec<u16> {
    bytes.chunks_exact(2).map(|c| f([c[0], c[1]])).collect()
}

const CR: u16 = b'\r' as u16;
const LF: u16 = b'\n' as u16;

/// Какой перевод строки встречается чаще всего. Без переводов строк — CRLF.
pub fn detect_eol(units: &[u16]) -> Eol {
    let (mut crlf, mut lf, mut cr) = (0usize, 0usize, 0usize);
    let mut i = 0;
    while i < units.len() {
        match units[i] {
            CR if units.get(i + 1) == Some(&LF) => {
                crlf += 1;
                i += 1;
            }
            CR => cr += 1,
            LF => lf += 1,
            _ => {}
        }
        i += 1;
    }
    if lf > crlf && lf >= cr {
        Eol::Lf
    } else if cr > crlf && cr > lf {
        Eol::Cr
    } else {
        Eol::CrLf
    }
}

/// Любые переводы строк → CRLF (EDIT-контрол понимает только их).
pub fn to_crlf(units: &[u16]) -> Vec<u16> {
    let mut out = Vec::with_capacity(units.len() + units.len() / 16);
    let mut i = 0;
    while i < units.len() {
        match units[i] {
            CR => {
                out.extend_from_slice(&[CR, LF]);
                if units.get(i + 1) == Some(&LF) {
                    i += 1;
                }
            }
            LF => out.extend_from_slice(&[CR, LF]),
            u => out.push(u),
        }
        i += 1;
    }
    out
}

/// CRLF → выбранный перевод строки.
pub fn from_crlf(units: &[u16], eol: Eol) -> Vec<u16> {
    if eol == Eol::CrLf {
        return units.to_vec();
    }
    let nl = if eol == Eol::Lf { LF } else { CR };
    let mut out = Vec::with_capacity(units.len());
    let mut i = 0;
    while i < units.len() {
        if units[i] == CR && units.get(i + 1) == Some(&LF) {
            out.push(nl);
            i += 2;
        } else {
            out.push(units[i]);
            i += 1;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn u(s: &str) -> Vec<u16> {
        s.encode_utf16().collect()
    }
    fn no_ansi_dec(_: &[u8]) -> Vec<u16> {
        panic!("ANSI не ожидался")
    }
    fn no_ansi_enc(_: &[u16]) -> Vec<u8> {
        panic!("ANSI не ожидался")
    }

    #[test]
    fn utf8_plain_and_lf() {
        let d = decode("привет\nмир\n".as_bytes(), no_ansi_dec);
        assert_eq!(d.encoding, Encoding::Utf8);
        assert_eq!(d.eol, Eol::Lf);
        assert_eq!(d.text, u("привет\r\nмир\r\n"));
    }

    #[test]
    fn boms() {
        let mut b = vec![0xEF, 0xBB, 0xBF];
        b.extend_from_slice("ё".as_bytes());
        assert_eq!(decode(&b, no_ansi_dec).encoding, Encoding::Utf8Bom);

        let le = encode(&u("Ж\r\n"), Encoding::Utf16Le, Eol::CrLf, no_ansi_enc);
        assert_eq!(&le[..2], &[0xFF, 0xFE]);
        let d = decode(&le, no_ansi_dec);
        assert_eq!((d.encoding, d.eol), (Encoding::Utf16Le, Eol::CrLf));
        assert_eq!(d.text, u("Ж\r\n"));

        let be = encode(&u("Ж"), Encoding::Utf16Be, Eol::CrLf, no_ansi_enc);
        assert_eq!(be, vec![0xFE, 0xFF, 0x04, 0x16]);
        assert_eq!(decode(&be, no_ansi_dec).text, u("Ж"));
    }

    #[test]
    fn invalid_utf8_falls_back_to_ansi() {
        // «Да» в Windows-1251
        let d = decode(&[0xC4, 0xE0], |b| b.iter().map(|&x| x as u16 + 0x350).collect());
        assert_eq!(d.encoding, Encoding::Ansi);
        assert_eq!(d.text, u("Да"));
    }

    #[test]
    fn eol_roundtrip() {
        for (src, eol) in [("a\r\nb\r\n", Eol::CrLf), ("a\nb\n", Eol::Lf), ("a\rb\r", Eol::Cr)] {
            let d = decode(src.as_bytes(), no_ansi_dec);
            assert_eq!(d.eol, eol, "{src:?}");
            assert_eq!(d.text, u("a\r\nb\r\n"));
            assert_eq!(encode(&d.text, d.encoding, d.eol, no_ansi_enc), src.as_bytes());
        }
    }

    #[test]
    fn mixed_eol_majority() {
        assert_eq!(detect_eol(&u("a\nb\nc\r\n")), Eol::Lf);
        assert_eq!(detect_eol(&u("one line")), Eol::CrLf);
        assert_eq!(to_crlf(&u("a\r\r\nb\n\n")), u("a\r\n\r\nb\r\n\r\n"));
    }
}
