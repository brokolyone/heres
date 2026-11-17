/* Лицензионное соглашение (EULA). G.EULA[lang] — строка; '#' в начале строки = заголовок раздела. */
(function () {
'use strict';
const G = window.G;
G.EULA = G.EULA || {};

G.EULA.en =
'#END USER LICENSE AGREEMENT\n' +
'FOR THE DEFENSE («Слово защиты»)\n' +
'Last updated: November 2026\n\n' +
'PLEASE READ THIS AGREEMENT CAREFULLY. BY STARTING, INSTALLING OR PLAYING THE GAME YOU AGREE TO BE BOUND BY ITS TERMS. IF YOU DO NOT AGREE, DO NOT USE THE GAME.\n\n' +
'#1. DEFINITIONS\n' +
'"Game" means the software «For the Defense / Слово защиты», including its code, graphics, fonts, music, sound effects, text, story, characters and any updates. "Licensor" means the authors and publisher of the Game. "You" means the individual using the Game.\n\n' +
'#2. LICENSE GRANT\n' +
'Subject to this Agreement, the Licensor grants you a personal, limited, non-exclusive, non-transferable, revocable license to run the Game for your own non-commercial entertainment on devices you own or control.\n\n' +
'#3. RESTRICTIONS\n' +
'You may not, except where applicable law expressly permits it:\n' +
'(a) sell, rent, lease, sublicense or otherwise commercially exploit the Game;\n' +
'(b) copy, redistribute or make the Game available on a network for use by others;\n' +
'(c) modify, translate or create derivative works of the Game, other than personal mods that are not distributed;\n' +
'(d) decompile, reverse engineer or disassemble the Game;\n' +
'(e) remove or alter any copyright notices, credits or this Agreement;\n' +
'(f) use the Game for any unlawful purpose.\n' +
'Recording and streaming gameplay and publishing screenshots for non-commercial or ad-supported channels is permitted, provided that the Game is credited.\n\n' +
'#4. OWNERSHIP\n' +
'The Game is licensed, not sold. The Licensor retains all right, title and interest in and to the Game, including all intellectual property rights. All rights not expressly granted are reserved.\n\n' +
'#5. THIRD-PARTY COMPONENTS\n' +
'The Game includes instrument samples from FluidR3 GM by Frank Wen, licensed under Creative Commons Attribution 3.0 (CC BY 3.0), distributed via the gleitz/midi-js-soundfonts project. Such components are subject to their own license terms, which prevail over this Agreement for those components. Summaries of California statutes refer to public law, which is not owned by the Licensor.\n\n' +
'#6. NO LEGAL ADVICE\n' +
'The Game is a work of fiction for entertainment. Descriptions of the law, courts and legal procedure are simplified, may be inaccurate or outdated, and do not constitute legal advice. No attorney-client relationship is created by using the Game. Consult a licensed attorney for advice on any legal matter.\n\n' +
'#7. FICTION\n' +
'All characters, organizations and events are fictional. Any resemblance to actual persons, living or dead, or actual events is purely coincidental.\n\n' +
'#8. USER DATA\n' +
'The Game stores settings and progress locally on your device (browser storage). The Game does not collect personal data and does not transmit your progress to the Licensor.\n\n' +
'#9. DISCLAIMER OF WARRANTIES\n' +
'THE GAME IS PROVIDED "AS IS" AND "AS AVAILABLE", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. THE LICENSOR DOES NOT WARRANT THAT THE GAME WILL BE UNINTERRUPTED OR ERROR-FREE.\n\n' +
'#10. LIMITATION OF LIABILITY\n' +
'TO THE MAXIMUM EXTENT PERMITTED BY LAW, IN NO EVENT SHALL THE LICENSOR BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE DAMAGES, OR FOR LOSS OF DATA, PROFITS OR GOODWILL, ARISING OUT OF OR RELATED TO THE GAME, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. THE LICENSOR\'S TOTAL LIABILITY SHALL NOT EXCEED THE AMOUNT YOU PAID FOR THE GAME, IF ANY.\n\n' +
'#11. TERMINATION\n' +
'This license is effective until terminated. It terminates automatically if you breach any of its terms. Upon termination you must stop using the Game and delete all copies. Sections 4–7 and 9–13 survive termination.\n\n' +
'#12. GOVERNING LAW\n' +
'This Agreement is governed by the laws of the State of California, United States, without regard to its conflict-of-laws rules. Any dispute shall be brought exclusively in the state or federal courts located in Los Angeles County, California, unless the mandatory consumer law of your country of residence provides otherwise.\n\n' +
'#13. MISCELLANEOUS\n' +
'If any provision is held unenforceable, the remaining provisions remain in full force. This Agreement is the entire agreement between you and the Licensor regarding the Game. The Licensor may update this Agreement; continued use after an update means acceptance.\n\n' +
'#14. CONTACT\n' +
'Questions about this Agreement: [contact e-mail to be provided by the publisher].';

G.EULA.ru =
'#ЛИЦЕНЗИОННОЕ СОГЛАШЕНИЕ С КОНЕЧНЫМ ПОЛЬЗОВАТЕЛЕМ\n' +
'«Слово защиты» (For the Defense)\n' +
'Редакция: ноябрь 2026 г.\n\n' +
'ВНИМАТЕЛЬНО ПРОЧИТАЙТЕ НАСТОЯЩЕЕ СОГЛАШЕНИЕ. ЗАПУСКАЯ, УСТАНАВЛИВАЯ ИЛИ ИСПОЛЬЗУЯ ИГРУ, ВЫ СОГЛАШАЕТЕСЬ С ЕГО УСЛОВИЯМИ. ЕСЛИ ВЫ НЕ СОГЛАСНЫ, НЕ ИСПОЛЬЗУЙТЕ ИГРУ.\n\n' +
'#1. ОПРЕДЕЛЕНИЯ\n' +
'«Игра» — программа «Слово защиты / For the Defense», включая код, графику, шрифты, музыку, звуковые эффекты, тексты, сюжет, персонажей и все обновления. «Лицензиар» — авторы и издатель Игры. «Вы» — физическое лицо, использующее Игру.\n\n' +
'#2. ПРЕДОСТАВЛЕНИЕ ЛИЦЕНЗИИ\n' +
'На условиях настоящего Соглашения Лицензиар предоставляет вам личную, ограниченную, неисключительную, непередаваемую и отзывную лицензию на запуск Игры для собственного некоммерческого досуга на принадлежащих вам или контролируемых вами устройствах.\n\n' +
'#3. ОГРАНИЧЕНИЯ\n' +
'Если иное прямо не разрешено применимым законом, вы не вправе:\n' +
'(а) продавать, сдавать в аренду, сублицензировать Игру или иначе извлекать из неё коммерческую выгоду;\n' +
'(б) копировать, распространять Игру или открывать к ней доступ по сети другим лицам;\n' +
'(в) изменять, переводить Игру или создавать производные произведения, кроме личных модификаций без распространения;\n' +
'(г) декомпилировать, дизассемблировать Игру или иначе восстанавливать её исходный код;\n' +
'(д) удалять или изменять уведомления об авторских правах, титры и настоящее Соглашение;\n' +
'(е) использовать Игру в незаконных целях.\n' +
'Разрешается записывать и транслировать игровой процесс и публиковать снимки экрана на некоммерческих каналах и каналах с рекламой при условии указания названия Игры.\n\n' +
'#4. ПРАВА СОБСТВЕННОСТИ\n' +
'Игра не продаётся, а предоставляется по лицензии. Все права на Игру, включая права интеллектуальной собственности, сохраняются за Лицензиаром. Права, прямо не предоставленные вам, сохраняются за Лицензиаром.\n\n' +
'#5. СТОРОННИЕ КОМПОНЕНТЫ\n' +
'Игра использует сэмплы инструментов FluidR3 GM (автор Frank Wen) по лицензии Creative Commons Attribution 3.0 (CC BY 3.0), распространяемые проектом gleitz/midi-js-soundfonts. На такие компоненты распространяются их собственные лицензии, которые имеют приоритет над настоящим Соглашением в части этих компонентов. Пересказы статей законов Калифорнии основаны на открытом праве, которое не принадлежит Лицензиару.\n\n' +
'#6. НЕ ЮРИДИЧЕСКАЯ КОНСУЛЬТАЦИЯ\n' +
'Игра — художественное произведение для развлечения. Описания законов, судов и процедуры упрощены, могут быть неточными или устаревшими и не являются юридической консультацией. Использование Игры не создаёт отношений «адвокат — клиент». По любым правовым вопросам обращайтесь к лицензированному адвокату.\n\n' +
'#7. ВЫМЫСЕЛ\n' +
'Все персонажи, организации и события вымышлены. Любое сходство с реальными людьми, живыми или умершими, и реальными событиями случайно.\n\n' +
'#8. ДАННЫЕ ПОЛЬЗОВАТЕЛЯ\n' +
'Игра хранит настройки и прогресс локально на вашем устройстве (хранилище браузера). Игра не собирает персональные данные и не передаёт ваш прогресс Лицензиару.\n\n' +
'#9. ОТКАЗ ОТ ГАРАНТИЙ\n' +
'ИГРА ПРЕДОСТАВЛЯЕТСЯ «КАК ЕСТЬ» И «ПО МЕРЕ ДОСТУПНОСТИ», БЕЗ КАКИХ-ЛИБО ГАРАНТИЙ, ЯВНЫХ ИЛИ ПОДРАЗУМЕВАЕМЫХ, ВКЛЮЧАЯ ГАРАНТИИ ТОВАРНОЙ ПРИГОДНОСТИ, ПРИГОДНОСТИ ДЛЯ ОПРЕДЕЛЁННОЙ ЦЕЛИ И НЕНАРУШЕНИЯ ПРАВ. ЛИЦЕНЗИАР НЕ ГАРАНТИРУЕТ БЕСПЕРЕБОЙНУЮ И БЕЗОШИБОЧНУЮ РАБОТУ ИГРЫ.\n\n' +
'#10. ОГРАНИЧЕНИЕ ОТВЕТСТВЕННОСТИ\n' +
'В МАКСИМАЛЬНОЙ СТЕПЕНИ, ДОПУСТИМОЙ ЗАКОНОМ, ЛИЦЕНЗИАР НИ ПРИ КАКИХ ОБСТОЯТЕЛЬСТВАХ НЕ НЕСЁТ ОТВЕТСТВЕННОСТИ ЗА КОСВЕННЫЕ, СЛУЧАЙНЫЕ, ОСОБЫЕ, ПОСЛЕДУЮЩИЕ ИЛИ ШТРАФНЫЕ УБЫТКИ, А ТАКЖЕ ЗА ПОТЕРЮ ДАННЫХ, ПРИБЫЛИ ИЛИ ДЕЛОВОЙ РЕПУТАЦИИ, СВЯЗАННЫЕ С ИГРОЙ, ДАЖЕ ЕСЛИ ОН БЫЛ ПРЕДУПРЕЖДЁН О ВОЗМОЖНОСТИ ТАКИХ УБЫТКОВ. СОВОКУПНАЯ ОТВЕТСТВЕННОСТЬ ЛИЦЕНЗИАРА НЕ ПРЕВЫШАЕТ СУММЫ, УПЛАЧЕННОЙ ВАМИ ЗА ИГРУ (ЕСЛИ ТАКОВАЯ БЫЛА).\n\n' +
'#11. ПРЕКРАЩЕНИЕ\n' +
'Лицензия действует до её прекращения и прекращается автоматически при нарушении вами любого из условий. После прекращения вы обязаны прекратить использование Игры и удалить все её копии. Разделы 4–7 и 9–13 продолжают действовать после прекращения.\n\n' +
'#12. ПРИМЕНИМОЕ ПРАВО\n' +
'Настоящее Соглашение регулируется законодательством штата Калифорния (США) без учёта коллизионных норм. Споры подлежат рассмотрению исключительно в судах штата или федеральных судах, расположенных в округе Лос-Анджелес, Калифорния, если императивные нормы о защите прав потребителей страны вашего проживания не предусматривают иное.\n\n' +
'#13. ПРОЧИЕ УСЛОВИЯ\n' +
'Если какое-либо положение будет признано недействительным, остальные положения сохраняют силу. Настоящее Соглашение составляет полное соглашение между вами и Лицензиаром в отношении Игры. Лицензиар вправе обновлять Соглашение; продолжение использования Игры после обновления означает согласие с ним.\n\n' +
'#14. КОНТАКТЫ\n' +
'Вопросы о Соглашении: [адрес электронной почты будет указан издателем].';
})();
