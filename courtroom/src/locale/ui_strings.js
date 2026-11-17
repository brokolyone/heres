/* Строки интерфейса «Слово защиты». G.T('key'). Языки: en (по умолчанию), ru; zh добавит переводчик по этим ключам. */
(function () {
'use strict';
const G = window.G;
G.UIStr = G.UIStr || { en: {}, ru: {}, zh: {} };

const en = {
  'logo': 'FOR THE DEFENSE',
  'menu.subtitle': 'Superior Court of California • County of Los Angeles',
  'menu.new': 'New game', 'menu.continue': 'Continue', 'menu.select': 'Select case',
  'menu.settings': 'Settings', 'menu.about': 'About',
  'common.back': 'Back', 'common.close': 'Close', 'common.on': 'On', 'common.off': 'Off',
  'common.clickBack': 'Click or press any key to go back',
  'common.scroll': '↑/↓, wheel or drag to scroll • Esc — back',

  'rec.title': 'CASE FILE', 'rec.tab': 'Evidence', 'rec.presentHint': 'PRESENT EVIDENCE',
  'rec.item': 'Exhibit', 'rec.hasDoc': '+ document', 'rec.empty': 'The file is empty',
  'rec.present': 'Present', 'rec.doc': 'Document', 'rec.close': 'Close',
  'doc.header': 'SUPERIOR COURT OF CALIFORNIA • COUNTY OF LOS ANGELES',
  'doc.close': 'Esc / click', 'doc.sign': 'Signature',

  'shout.objection': 'OBJECTION!', 'shout.contradiction': 'CONTRADICTION',
  'shout.sustained': 'SUSTAINED', 'shout.overruled': 'OVERRULED', 'shout.evidence': 'ADMITTED\nINTO EVIDENCE',
  'item.new': 'NEW EVIDENCE', 'item.stamp': 'ADMITTED',

  'hud.title': 'CROSS-EXAMINATION', 'hud.stmt': 'Statement {i}/{n}',
  'hud.press': 'Press', 'hud.present': 'Present', 'hud.record': 'File',

  'sel.title': 'SELECT CASE', 'sel.case': 'CASE № {n}', 'sel.locked': 'Locked: win the previous case first',
  'sel.done': 'Won. ', 'stamp.acq': 'ACQUITTED', 'stamp.acqF': 'ACQUITTED', 'sel.secret': '* * *',

  'set.title': 'SETTINGS',
  'set.tab.display': 'Display', 'set.tab.text': 'Text', 'set.tab.audio': 'Audio', 'set.tab.game': 'Gameplay',
  'set.tab.content': 'Content', 'set.tab.controls': 'Controls', 'set.tab.about': 'About', 'set.tab.eula': 'EULA',
  'set.tab.licenses': 'Licenses',
  'set.scaleMode': 'Scaling', 'scale.integer': 'Integer', 'scale.fit': 'Fit window', 'scale.fixed': 'Fixed',
  'set.scale': 'Fixed scale', 'set.fullscreen': 'Fullscreen', 'set.shake': 'Screen shake', 'set.flash': 'Flashes',
  'set.lang': 'Language', 'set.textSize': 'Text size', 'size.normal': 'Normal', 'size.large': 'Large',
  'set.textSpeed': 'Text speed', 'set.auto': 'Auto-advance',
  'set.music': 'Music', 'set.sfx': 'Sound effects', 'set.blips': 'Voice blips',
  'set.difficulty': 'Difficulty', 'diff.easy': 'Easy · 7 seals', 'diff.normal': 'Normal · 5 seals', 'diff.hard': 'Hard · 3 seals',
  'set.diffNote': 'Seals = how many mistakes the judge will tolerate.',
  'set.adult': 'Adult language', 'set.adultNote': 'Rude remarks from the gallery. Never slurs.',
  'set.preview': 'Objection sustained. Proceed, counsel.',
  'set.openAbout': 'Open «About»', 'set.openEula': 'Read the EULA',
  'set.hint': '←/→ tabs • ↑/↓ option • Enter/←/→ change • Esc back',
  'ctl.title': 'Keyboard • mouse • touch',
  'ctl.list': 'Enter / Space / click — next line, confirm\n' +
    '← / → — previous / next statement\n' +
    'Q — press the witness\n' +
    'E — present evidence\n' +
    'R / Tab — open the case file\n' +
    '↑ ↓ ← → — move selection in menus and the file\n' +
    'Esc — pause menu, close, back\n' +
    '1–4 — pick an answer\n' +
    'Touch: tap = click, drag sliders and lists',
  'lic.body': 'FOR THE DEFENSE — all code, pixel art, fonts, sound design and story were made for this project.\n\n' +
    'Instrument samples: FluidR3 GM by Frank Wen, licensed under Creative Commons Attribution 3.0 (CC BY 3.0), ' +
    'distributed via gleitz/midi-js-soundfonts.\n\n' +
    'Statute summaries are paraphrases of public California law (Penal Code, Evidence Code). ' +
    'Statutes themselves are public domain.\n\n' +
    'No other third-party code, images or fonts are used.',

  'pause.title': 'RECESS', 'pause.resume': 'Resume', 'pause.record': 'Case file', 'pause.rep': 'Reputation',
  'pause.settings': 'Settings', 'pause.restart': 'Restart case', 'pause.menu': 'Main menu',
  'pause.sub': 'The court is in recess',

  'rep.title': 'Reputation of Daniel Reed', 'rep.graph': 'reputation over cases', 'rep.total': 'TOTAL',
  'rep.win': 'won', 'rep.loss': 'lost', 'rep.opinions': 'What they think of you',
  'rep.judge': 'Judge', 'rep.jury': 'Jury', 'rep.public': 'Public', 'rep.press': 'Press',
  'rep.close': 'Close', 'rep.none': 'No cases yet — sample data', 'rep.case': 'Case',

  'lang.choose': 'Choose your language',
  'menu.rep': 'Reputation',
  'rep.tier0': 'Intern', 'rep.tier1': 'Rookie defender', 'rep.tier2': 'Defense attorney',
  'rep.tier3': 'Seasoned counsel', 'rep.tier4': 'Bane of prosecutors', 'rep.tier5': 'Legend of the Bar',
  'rep.p.win': 'win', 'rep.p.loss': 'loss', 'rep.p.cred': 'judge\'s trust', 'rep.p.routes': 'alt. lines',
  'rep.p.argue': 'arguments', 'rep.p.mistakes': 'mistakes', 'rep.p.crowd': 'public & press', 'rep.p.court': 'judge & jury',
  'rep.rank': 'Rank', 'rep.wl': '{w} won · {l} lost',

  'arg.title': 'BUILD THE ARGUMENT', 'arg.claim': 'Claim', 'arg.ground': 'Legal basis', 'arg.proof': 'Evidence',
  'arg.submit': 'Argue', 'arg.back': 'Back', 'arg.pick': '— choose —', 'arg.noProof': 'no exhibit needed',
  'arg.preview': 'The defense contends that {claim}, because {ground} ({law}), as shown by: {ev}.',
  'arg.previewNoEv': 'The defense contends that {claim}, because {ground} ({law}).',
  'arg.step': 'Step {i}/3',

  'about.title': 'ABOUT THE GAME',
  'about.body':
'#FOR THE DEFENSE\n' +
'A pixel-art courtroom drama in four cases.\n\n' +
'#WHAT THIS GAME IS\n' +
'You are Daniel Reed, a defense attorney in Los Angeles. In every case your client is charged with a felony, and you are the only one standing between them and a guilty verdict. You do not fight with fists: you fight with *questions*, *evidence* and *law*.\n\n' +
'#THE REAL AMERICAN LEGAL SYSTEM\n' +
'Cases are tried in the Superior Court of California, County of Los Angeles — the real trial court of the county. The prosecution is "The People of the State of California", represented by a Deputy District Attorney. The burden of proof is on the People: the defendant is presumed innocent, and the jury must be convinced *beyond a reasonable doubt*. A verdict in a criminal case must be unanimous.\n\n' +
'#STATUTES USED\n' +
'Charges and rules quote real California law, paraphrased. Text follows the editions in force on 1 January 2025:\n' +
'• Cal. Penal Code § 487(a) — grand theft (property over $950).\n' +
'• Cal. Penal Code § 451(c) — arson of a structure.\n' +
'• Cal. Penal Code § 594(a), (b)(1) — vandalism, damage of $400 or more.\n' +
'• Cal. Penal Code § 187(a) — murder (as amended by SB 1437, 2018).\n' +
'• Cal. Penal Code § 550(a)(1) — insurance fraud.\n' +
'• Cal. Evidence Code § 702 — personal knowledge of a witness.\n' +
'• Cal. Evidence Code § 765 — the court controls the questioning.\n' +
'• Cal. Evidence Code § 767 — leading questions.\n' +
'• Cal. Evidence Code § 776 — calling an adverse party.\n' +
'• Cal. Evidence Code § 800 — lay opinion testimony.\n' +
'• Cal. Evidence Code § 1200 — the hearsay rule.\n' +
'Summaries are simplified for play. They are not the official text.\n\n' +
'#HOW A TRIAL WORKS HERE\n' +
'1. Jail visit — you meet your client and learn their story.\n' +
'2. The court is called to order; the prosecution gives its opening statement.\n' +
'3. The clerk swears in a witness; the prosecutor conducts direct examination.\n' +
'4. *Cross-examination* — your turn. Go through the testimony statement by statement. *Press* (Q) to ask for details; *present* evidence (E) when a statement contradicts it.\n' +
'5. Objections: either side may object. The judge rules "sustained" or "overruled".\n' +
'6. Twists, a breakdown, closing — and the verdict of the jury.\n' +
'Each mistake costs one seal of the judge\'s patience. Lose them all and the trial ends badly.\n\n' +
'#THE ARGUMENT BUILDER\n' +
'At key moments you build the argument yourself, like a real lawyer: choose a *claim*, the *legal basis* (an actual rule of evidence or a statute) and the *exhibit* that proves it. Several different routes can be correct, and each leads to its own consequences. Weak combinations pass with a penalty; wrong ones are rejected by the judge with an explanation.\n\n' +
'#REPUTATION\n' +
'After every case your reputation is recalculated:\n' +
'Score = 100 × difficulty for a win (−80 ÷ difficulty for a loss) + 12 × seals left + 15 per alternative line + 10 per argument − 10 per mistake + 2 × (public + press) + (judge + jury). Difficulty: easy 0.8, normal 1.0, hard 1.4.\n' +
'Four groups hold opinions about you, from −10 to +10: the *judge*, the *jury*, the *public* and the *press*. Clever legal moves impress the judge; theatrics win the gallery; the press loves a twist.\n\n' +
'#CONTROLS\n' +
'Enter / Space / click — next line. ← → — statements. Q — press. E — present. R / Tab — case file. Esc — pause. The game is fully playable with mouse, keyboard or touch.\n\n' +
'#CREDITS\n' +
'Story, code, pixel art, bitmap fonts, music and sound design were made from scratch for this project by a team of Claude Code agents.\n' +
'Instrument samples: FluidR3 GM by Frank Wen (CC BY 3.0) via gleitz/midi-js-soundfonts.\n\n' +
'#DISCLAIMER\n' +
'All characters, companies and events are fictional. Any resemblance to real persons is coincidental. Statute summaries are simplified and may be out of date. *This game is not legal advice.* If you need legal help, talk to a licensed attorney.',
};

const ru = {
  'logo': 'СЛОВО ЗАЩИТЫ',
  'menu.subtitle': 'Высший суд Калифорнии • Округ Лос-Анджелес',
  'menu.new': 'Новая игра', 'menu.continue': 'Продолжить', 'menu.select': 'Выбор дела',
  'menu.settings': 'Настройки', 'menu.about': 'Об игре',
  'common.back': 'Назад', 'common.close': 'Закрыть', 'common.on': 'Вкл.', 'common.off': 'Выкл.',
  'common.clickBack': 'Нажмите, чтобы вернуться',
  'common.scroll': '↑/↓, колесо или перетаскивание • Esc — назад',

  'rec.title': 'МАТЕРИАЛЫ ДЕЛА', 'rec.tab': 'Улики', 'rec.presentHint': 'ПРЕДЪЯВИТЕ УЛИКУ',
  'rec.item': 'Улика', 'rec.hasDoc': '+ документ', 'rec.empty': 'Папка пуста',
  'rec.present': 'Предъявить', 'rec.doc': 'Документ', 'rec.close': 'Закрыть',
  'doc.header': 'ВЫСШИЙ СУД КАЛИФОРНИИ • ОКРУГ ЛОС-АНДЖЕЛЕС',
  'doc.close': 'Esc / клик', 'doc.sign': 'Подпись',

  'shout.objection': 'ПРОТЕСТ!', 'shout.contradiction': 'ПРОТИВОРЕЧИЕ',
  'shout.sustained': 'ПРОТЕСТ\nПРИНЯТ', 'shout.overruled': 'ПРОТЕСТ\nОТКЛОНЁН', 'shout.evidence': 'ПРИОБЩЕНО\nК ДЕЛУ',
  'item.new': 'НОВАЯ УЛИКА', 'item.stamp': 'ПРИОБЩЕНО',

  'hud.title': 'ПЕРЕКРЁСТНЫЙ ДОПРОС', 'hud.stmt': 'Показание {i}/{n}',
  'hud.press': 'Уточнить', 'hud.present': 'Предъявить', 'hud.record': 'Папка',

  'sel.title': 'ВЫБОР ДЕЛА', 'sel.case': 'ДЕЛО № {n}', 'sel.locked': 'Дело закрыто: сначала выиграйте предыдущее',
  'sel.done': 'Выиграно. ', 'stamp.acq': 'ОПРАВДАН', 'stamp.acqF': 'ОПРАВДАНА', 'sel.secret': '* * *',

  'set.title': 'НАСТРОЙКИ',
  'set.tab.display': 'Экран', 'set.tab.text': 'Текст', 'set.tab.audio': 'Звук', 'set.tab.game': 'Игра',
  'set.tab.content': 'Контент', 'set.tab.controls': 'Управление', 'set.tab.about': 'Об игре', 'set.tab.eula': 'Соглашение',
  'set.tab.licenses': 'Лицензии',
  'set.scaleMode': 'Масштаб', 'scale.integer': 'Целый', 'scale.fit': 'По окну', 'scale.fixed': 'Фиксированный',
  'set.scale': 'Множитель', 'set.fullscreen': 'Полный экран', 'set.shake': 'Тряска экрана', 'set.flash': 'Вспышки',
  'set.lang': 'Язык', 'set.textSize': 'Размер текста', 'size.normal': 'Обычный', 'size.large': 'Крупный',
  'set.textSpeed': 'Скорость текста', 'set.auto': 'Автопрокрутка',
  'set.music': 'Музыка', 'set.sfx': 'Звуки', 'set.blips': 'Голоса (блипы)',
  'set.difficulty': 'Сложность', 'diff.easy': 'Лёгкая · 7 печатей', 'diff.normal': 'Обычная · 5 печатей', 'diff.hard': 'Трудная · 3 печати',
  'set.diffNote': 'Печати — сколько ошибок стерпит судья.',
  'set.adult': 'Взрослый язык', 'set.adultNote': 'Грубые реплики из зала. Без оскорблений групп.',
  'set.preview': 'Протест принят. Продолжайте, советник.',
  'set.openAbout': 'Открыть «Об игре»', 'set.openEula': 'Читать соглашение',
  'set.hint': '←/→ вкладки • ↑/↓ пункт • Enter/←/→ изменить • Esc назад',
  'ctl.title': 'Клавиатура • мышь • касание',
  'ctl.list': 'Enter / Пробел / клик — следующая реплика, подтвердить\n' +
    '← / → — предыдущее / следующее показание\n' +
    'Q — уточнить показание\n' +
    'E — предъявить улику\n' +
    'R / Tab — открыть папку дела\n' +
    '↑ ↓ ← → — выбор в меню и в папке\n' +
    'Esc — пауза, закрыть, назад\n' +
    '1–4 — выбрать ответ\n' +
    'Касание: тап = клик, ползунки и списки тянутся пальцем',
  'lic.body': '«Слово защиты»: весь код, пиксель-арт, шрифты, звук и сценарий созданы для этого проекта.\n\n' +
    'Сэмплы инструментов: FluidR3 GM, автор Frank Wen, лицензия Creative Commons Attribution 3.0 (CC BY 3.0), ' +
    'распространяется через gleitz/midi-js-soundfonts.\n\n' +
    'Пересказы статей основаны на открытом праве Калифорнии (Penal Code, Evidence Code). ' +
    'Тексты законов являются общественным достоянием.\n\n' +
    'Другого стороннего кода, изображений и шрифтов в игре нет.',

  'pause.title': 'ПЕРЕРЫВ', 'pause.resume': 'Продолжить', 'pause.record': 'Папка дела', 'pause.rep': 'Репутация',
  'pause.settings': 'Настройки', 'pause.restart': 'Начать дело заново', 'pause.menu': 'Главное меню',
  'pause.sub': 'В заседании объявлен перерыв',

  'rep.title': 'Репутация Дэниела Рида', 'rep.graph': 'репутация по делам', 'rep.total': 'ИТОГО',
  'rep.win': 'победа', 'rep.loss': 'поражение', 'rep.opinions': 'Что о вас думают',
  'rep.judge': 'Судья', 'rep.jury': 'Присяжные', 'rep.public': 'Публика', 'rep.press': 'Пресса',
  'rep.close': 'Закрыть', 'rep.none': 'Дел пока нет — пример', 'rep.case': 'Дело',

  'lang.choose': 'Выберите язык',
  'menu.rep': 'Репутация',
  'rep.tier0': 'Стажёр', 'rep.tier1': 'Начинающий защитник', 'rep.tier2': 'Защитник',
  'rep.tier3': 'Опытный адвокат', 'rep.tier4': 'Гроза прокуроров', 'rep.tier5': 'Легенда коллегии',
  'rep.p.win': 'победа', 'rep.p.loss': 'поражение', 'rep.p.cred': 'доверие суда', 'rep.p.routes': 'др. линии',
  'rep.p.argue': 'аргументы', 'rep.p.mistakes': 'ошибки', 'rep.p.crowd': 'публика и пресса', 'rep.p.court': 'судья и присяжные',
  'rep.rank': 'Звание', 'rep.wl': 'побед: {w} · поражений: {l}',

  'arg.title': 'ПОСТРОЙТЕ АРГУМЕНТ', 'arg.claim': 'Тезис', 'arg.ground': 'Правовое основание', 'arg.proof': 'Доказательство',
  'arg.submit': 'Заявить', 'arg.back': 'Назад', 'arg.pick': '— выберите —', 'arg.noProof': 'улика не нужна',
  'arg.preview': 'Защита утверждает, что {claim}, поскольку {ground} ({law}), что подтверждается: {ev}.',
  'arg.previewNoEv': 'Защита утверждает, что {claim}, поскольку {ground} ({law}).',
  'arg.step': 'Шаг {i}/3',

  'about.title': 'ОБ ИГРЕ',
  'about.body':
'#СЛОВО ЗАЩИТЫ\n' +
'Пиксельная судебная драма в четырёх делах.\n\n' +
'#ЧТО ЭТО ЗА ИГРА\n' +
'Вы — Дэниел Рид, адвокат защиты в Лос-Анджелесе. В каждом деле вашему клиенту грозит обвинение в тяжком преступлении, и только вы стоите между ним и обвинительным вердиктом. Ваше оружие — *вопросы*, *улики* и *закон*.\n\n' +
'#НАСТОЯЩАЯ АМЕРИКАНСКАЯ СИСТЕМА\n' +
'Дела слушаются в Высшем суде Калифорнии по округу Лос-Анджелес — это реальный суд первой инстанции. Обвинение представляет «Народ штата Калифорния» в лице заместителя окружного прокурора. Бремя доказывания лежит на обвинении: подсудимый считается невиновным, пока присяжные не убеждены в его вине *вне разумных сомнений*. Вердикт по уголовному делу должен быть единогласным.\n\n' +
'#КАКИЕ ЗАКОНЫ ИСПОЛЬЗУЮТСЯ\n' +
'Обвинения и правила опираются на настоящие законы Калифорнии в пересказе, в редакции, действующей на 1 января 2025 г.:\n' +
'• Cal. Penal Code § 487(a) — хищение в крупном размере (свыше 950 $).\n' +
'• Cal. Penal Code § 451(c) — поджог строения.\n' +
'• Cal. Penal Code § 594(a), (b)(1) — вандализм с ущербом от 400 $.\n' +
'• Cal. Penal Code § 187(a) — убийство (с изменениями SB 1437, 2018).\n' +
'• Cal. Penal Code § 550(a)(1) — страховое мошенничество.\n' +
'• Cal. Evidence Code § 702 — личная осведомлённость свидетеля.\n' +
'• Cal. Evidence Code § 765 — суд контролирует допрос.\n' +
'• Cal. Evidence Code § 767 — наводящие вопросы.\n' +
'• Cal. Evidence Code § 776 — вызов противной стороны.\n' +
'• Cal. Evidence Code § 800 — мнение свидетеля-неспециалиста.\n' +
'• Cal. Evidence Code § 1200 — правило о показаниях с чужих слов (hearsay).\n' +
'Пересказы упрощены для игры и не являются официальным текстом.\n\n' +
'#КАК ИДЁТ ПРОЦЕСС\n' +
'1. Свидание в тюрьме — вы узнаёте версию клиента.\n' +
'2. Открытие заседания, вступительная речь обвинения.\n' +
'3. Секретарь приводит свидетеля к присяге, прокурор ведёт прямой допрос.\n' +
'4. *Перекрёстный допрос* — ваш ход. Идите по показаниям одно за другим. *Уточняйте* (Q), чтобы вытянуть детали, и *предъявляйте* улику (E), когда показание ей противоречит.\n' +
'5. Протесты: любая сторона может заявить протест, судья решает — «принят» или «отклонён».\n' +
'6. Повороты, срыв свидетеля, заключительные речи — и вердикт присяжных.\n' +
'Каждая ошибка стоит одной печати терпения судьи. Потеряете все — процесс закончится плохо.\n\n' +
'#КОНСТРУКТОР АРГУМЕНТА\n' +
'В ключевые моменты вы сами собираете аргумент, как настоящий юрист: выбираете *тезис*, *правовое основание* (реальную норму о доказательствах или статью) и *улику*, которая это подтверждает. Верных путей бывает несколько, и у каждого свои последствия. Слабые сочетания проходят со штрафом, неверные судья отклоняет и объясняет почему.\n\n' +
'#РЕПУТАЦИЯ\n' +
'После каждого дела репутация пересчитывается:\n' +
'Очки = 100 × сложность за победу (−80 ÷ сложность за поражение) + 12 × оставшиеся печати + 15 за каждую альтернативную линию + 10 за аргумент − 10 за ошибку + 2 × (публика + пресса) + (судья + присяжные). Сложность: лёгкая 0,8, обычная 1,0, трудная 1,4.\n' +
'Мнение о вас складывается у четырёх групп, от −10 до +10: *судья*, *присяжные*, *публика* и *пресса*. Грамотные юридические ходы ценит судья, эффектные — зал, а пресса обожает повороты.\n\n' +
'#УПРАВЛЕНИЕ\n' +
'Enter / Пробел / клик — дальше. ← → — показания. Q — уточнить. E — предъявить. R / Tab — папка. Esc — пауза. Играть можно мышью, клавиатурой или касанием.\n\n' +
'#СОЗДАТЕЛИ\n' +
'Сценарий, код, пиксель-арт, растровые шрифты, музыка и звук созданы с нуля для этого проекта командой агентов Claude Code.\n' +
'Сэмплы инструментов: FluidR3 GM, автор Frank Wen (CC BY 3.0), через gleitz/midi-js-soundfonts.\n\n' +
'#ОГОВОРКА\n' +
'Все персонажи, компании и события вымышлены, любые совпадения случайны. Пересказы законов упрощены и могут устареть. *Игра не является юридической консультацией.* За юридической помощью обращайтесь к лицензированному адвокату.',
};

Object.assign(G.UIStr.en = G.UIStr.en || {}, en);
Object.assign(G.UIStr.ru = G.UIStr.ru || {}, ru);
G.UIStr.zh = G.UIStr.zh || {};
})();
