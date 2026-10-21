# Минимальная интеграция и границы семантики

Основание: commit2c7ad49cd4f4fa852168a8ce295bf739bf076adc, локальные pinned исходники.
Ничего в них не изменено/исполнено в этой попытке.

| Точка | Минимальная замена и сохраняемое свойство |
|---|---|
| MCTS103–106; Utils62–101 | Вместо materialize ReadPList подключить read-only хранилище к `$grams_with_pattern->[1]`, `$is_word`, `$maxlen`. Остальные порядки пусты при -n. |
| MCTS424–446 (также363–385 при spaced, вне выбранной области) | FETCH(pattern) возвращает весь исходный массив либо undef. SQL ORDER BY seq, конкатенация строк и дубли обязательны. |
| Utils76–84 | Словарь строится до fold order=1; только original-order1. Нельзя брать все слитые фразы или WLM1. |
| Utils86–98 | maxlen при -n по всем кандидатам всех исходных orders; здесь46. |
| NoSpace9–36; MCTS459 | FETCH(word) возвращает1/undef. Сначала целое слово; затем длины по убыванию, позиции по возрастанию, первый match, рекурсия и collapse whitespace. Не Viterbi и не глобальный выбор сегментации; неизвестные фрагменты сохраняются. |
| MCTS428–446 | Первая половина итераций использует source order, вторая стабильную сортировку по Utils::Sim; pl=50 только ПОСЛЕ этого. Дубликаты могут занимать места в50. |
| Utils123–129 | Сходство содержит деление com/length(x); эта арифметика должна остаться в Perl. В текущем адаптере её нет. |

Предпочтительная будущая граница: новая `CompactPatList::Attach` связывает два
read-only tied hash (FETCH/EXISTS) и integer maxlen. В mcts требуется только import
нового glue и замена строки106; solver не переносится. Текущий Python API —
проверяемое ядро хранения, НЕ такой готовый tied-hash Perl модуль. Ни патч, ни bridge
не исполнялись. При неподдерживаемых STORE/DELETE/iteration нужно явное исключение,
а не тихое изменение поведения. В просмотренном -n пути solver только читает эти
два hash; перечисления их ключей не найдено. Возвращаемые списки используются
для копии/sort, поэтому fresh array сохраняет логическое поведение, но не Perl identity.

В стандартных прочитанных /usr/share/perl5,/usr/lib/x86_64-linux-gnu/perl5,
/usr/lib/x86_64-linux-gnu/perl,/usr/share/perl не найдено DBI.pm/DBD/SQLite.pm.
Это не глобальное доказательство отсутствия. Нельзя объявить прямое DBI подключение
готовым или установить зависимости молча. Вариант без установки — отдельный own-stdlib
SQLite broker + тонкий Perl glue по строгому byte/list протоколу; это новые компоненты,
новый дочерний процесс и отдельный будущий freeze/approval, не текущий PASS.

Численные модели остаются вне адаптера: ReadLM20–55 хранит исходные probability
скаляры, при дублях ключа последняя запись заменяет прежнюю. JMSmoothing6–32
сохраняет Perl truthiness, unknown substitution, три произведения/порядок сложений,
log и последовательное накопление. JMSmoothing36–47 проверяет unknown по **WLM1**,
а не по `$is_word`; 51–62 сохраняет whitespace→underscore, char/word mixture0.05.
Нельзя переводить значения через Python float/SQLite REAL/округлённый JSON.
Шесть численных LM не конвертировались, их загрузка/память остаются отдельной границей.

Tie/hash-order: stable sort строки8/438 сохраняет source order равных similarity.
FreqAnalysis6–14 начинает с keys %c; MCTS268 сортирует scoring keys, но275 не сортирует
порядок добавления children; строгие `>` в188,226,303 сохраняют первый максимум.
Нужно удержать Perl5.38.2/arch,LC_ALL=C,PERL_HASH_SEED=2026101705,
PERL_PERTURB_KEYS=0; одних этих env недостаточно как доказательства trajectory equality.
Lazy allocations/IO могут менять время, а будущий bridge — структуру вызовов.
Порядок/полнота списков доказуемы отдельно от численной/траекторной эквивалентности.
Cache не должен превращать IO-error в missing, отбрасывать кандидатов, хранить top50
или сегментацию по неполному словарю. Нынешний API cache bounded; ошибки fatal.

Исходное условие перебора длины MCTS420 (`length(ctext)+sta`) и прочие странности
не исправляются адаптацией хранения. Изменение таких правил было бы отдельной версией.

Прямые первичные локаторы:
https://github.com/bmhauer/hhk-decipherment/blob/2c7ad49cd4f4fa852168a8ce295bf739bf076adc/Utils.pm#L62-L101
https://github.com/bmhauer/hhk-decipherment/blob/2c7ad49cd4f4fa852168a8ce295bf739bf076adc/NoSpace.pm#L9-L36
https://github.com/bmhauer/hhk-decipherment/blob/2c7ad49cd4f4fa852168a8ce295bf739bf076adc/masc_solver_mcts.pl#L406-L465
https://github.com/bmhauer/hhk-decipherment/blob/2c7ad49cd4f4fa852168a8ce295bf739bf076adc/JMSmoothing.pm#L6-L62
