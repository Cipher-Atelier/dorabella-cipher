# TS-INTEGRATION87-BOUND-v1 — доказанный блокер executable freeze

**BLOCKED_BEFORE_EXECUTABLE.** Подготовка выявила обязательный объём IPC-журнала, несовместимый с прежними 8 MiB/file и 32 MiB total. Новый broker/Perl/glue, solver, scorer и Dorabella не исполнялись. Старые caps, arithmetic, inputs и STOP не изменены. Это конкретное препятствие существующему транспорту, не доказательство невозможности 87-буквенного поиска.

## 1. Независимо выбранный новый контроль

Abraham Lincoln → Grace Bedell, **19 октября 1860**, второй абзац тела, начинающийся «I regret». Использована [опубликованная транскрипция Dickinson College](https://hd.housedivided.dickinson.edu/index.php/node/25339), с указанием Roy P. Basler, *Collected Works*, т.4, с.129 (1953), retrieved line39. [Каталог Library of Congress](https://www.loc.gov/exhibits/lincoln/candidate-lincoln.html#obj1) удостоверяет письмо/дату и loan от Benjamin Shapell Family Manuscript Foundation, объект070/digital ID al0070. Прочитанная [транскрипция LOC](https://www.loc.gov/exhibits/lincoln/ext/transcription20.html) публикует только фрагмент о бороде; она не выдаётся за полный текст выбранного абзаца. Факсимиле сейчас не разбиралось.

Правило зафиксировано **до модельного census**: из точного абзаца оставить только ASCII A–Z/a–z, lowercase, первые87, без padding/J→I/замены контроля. Выбранный фрагмент:

```
iregretthenecessityofsayingihavenodaughtersihavethreesonsoneseventeenonenineandoneseven
```

SHA256 plaintext bytes без LF:
`532c507d30b9e75f95bb553a4f1f5edeb7849470046759a85f38336c7c5f987f`.

Перестановка для plaintext alphabet `abcdefghijklmnopqrstuvwxyz`:
`wmeisnpzouaxfjgkyctbqdvlhr`.
Она получена единственным заранее заданным hash-sort букв по SHA256 UTF8(`TS-INTEGRATION87-v1|20261018|permutation|` + буква), ties по букве. Ни ключ, ни источник не выбирались по модели/score/target.

Ciphertext:
```
ocspcsbbzsjsesttobhgntwhojpozwdsjgiwqpzbsctozwdsbzcsstgjtgjstsdsjbssjgjsjojswjigjstsdsj
```

SHA256 ciphertext bytes без LF:
`87e43dcfb9528f99d798eed633452287e487a857c10fd1c662becdcc8823c79d`.
87 позиций, 16 встречающихся типов. Собственный прямой encoder и отдельная индексная inverse-проверка дали87/87; полные позиции — truth.json. Это **не blind recovery**.

В четырёх закреплённых инвентарях CH2/P01, CH3 RFC, 16 новых R6 и старых fraction inputs совпадение87-буквенного текста не найдено; paths/hashes сохранены. Это свежий контроль относительно этих проверенных списков, не доказательство отсутствия текста в NYT training corpus. Разработчик видит истину, будущий decoder должен получать только decoder_input.json; truth.json, источник, ключ и нормализатор не входят в его входы. Эта версия не содержит executable decoder.

## 2. Статически прослеженный оригинальный control flow

Исходный commit `2c7ad49cd4f4fa852168a8ce295bf739bf076adc`; masc_solver_mcts.pl SHA `5021fcef107d606f641fa4b24e4544bb3eeb159efefb26dc6d4d3966a7068f17`. В пакете точные reference copies и SOURCE_IDENTITIES.json; **изменений сторонних исходников нет**.

- `masc_solver_mcts.pl:81–106,117–143`: P — исходный frequency order; Pattern преобразует вход по первому появлению; GetSortedAlphabet считает встреченные буквы и сортирует по частотам; GetFreqKey сопоставляет им первые16 букв P. `FreqAnalysis.pm:6–14,28–43`: ties оставлены в Perl keys-order, не заменены алфавитной сортировкой. Точный root сейчас не вычислялся другим эмулятором Perl.
- `MCTS:154–204; Selection:208–232`: root value=-inf; на каждой из двух итераций Selection выбирает leaf, Expansion полностью строит successors и scores, затем strict > обновляет best и выполняется Backpropagation. Вторая итерация зависит от первой; раннего штатного budget-return нет.
- `GetSuccessorsNoSpace:419–460`: для каждого start0…85 length2…46. Условие именно `len <= length(ctext)+sta`, **не** остаток строки. Поэтому 86×45=3870 окон/итерацию; у конца многие len дают один укороченный suffix. Это поведение сохранено.
- Каждое окно делает guard FETCH (:425); при существующем списке первая итерация делает ещё FETCH(:430), вторая — ещё два (:435,:439). Полный список копируется/сортируется **до** pl50. Дубликаты сохраняются. `CompactPatList.pm:101–104` каждый FETCH вызывает request; Python LRU не отменяет передачу (:24–81).
- До score вызовы Assume, фильтры seen/key_value и NoSpace (:454–460) зависят от ключа. Expansion:268–300 оценивает distinct segmented strings в sorted order, затем обходит keys и применяет строгие сравнения. Не переписывать hash order/ties/arithmetics. `JMSmoothing.pm:19–29,36–62` остаётся оригинальным Perl.
- Единственная предполагаемая search-конфигурация: MCTS `-n -v -mi2 -pc1 -pl50 -cc0.05`, исходные шесть коэффициентов, PERL_HASH_SEED=`2026101705` (hex), PERL_PERTURB_KEYS=0. В коде нет search rand/srand. mi2 — минимальный исходный вариант, проходящий обе половины выбора списков; это bounded pilot, не доказанная чувствительность.

## 3. Что действительно выполнено собственным кодом

Одна finite data-only подготовка, не запуск pipeline: 30s cooperative, AS128MiB, CPU25/28s, ≤3871 SQL, cache2MiB; один процесс, без network/subprocess/foreign imports. До её запуска сохранены SELECTION_FREEZE и PREP_STATIC_FREEZE; frozen code SHA `dd5971925e0e467169432c1852a497806071fc599ea3ef8b30c719c258ffc791`.

Сначала проверены полные hashes исходного .patlst (340083717 B, `2849bc03f85c59a422f1945960ce04a4b6e66cc02c61a6484de0283c30c724fd`) и verified SQLite (537591808 B, `c35f28462555da9982ed975b713a291b654a0e2b0d514e7d498f717bdf386070`). Затем readonly SELECT агрегировал **только count/segments/longest** по 2465 уникальным patterns. Ни candidate strings, ни LM values не извлекались; индексы не перестраивались. Канонический pattern инвариантен относительно фиксированной инъективной перестановки, поэтому это те же patterns после original Pattern. Две собственные формы canonicalization сверены.

Фактический исход: exit0, **0.881966971s**, ru_maxrss **13700 KiB**. Raw tool response сохранён. Последующий собственный readback использовал только сохранённые агрегаты и сравнил их с raw stdout; SQL/encoder/search не повторялись.

## 4. Доказанные величины и их правильный смысл

Из3870 окон список есть в1283; сумма длин списков по окнам `C=5889191`; сумма `min(50,count)` по окнам `S=49737`.

| Величина для завершённых двух итераций | Значение | Тип основания |
|---|---:|---|
| List FETCH, без meta/close/membership | 11589 | Точно: 2×3870+3×1283 |
| Переданные вхождения строк списков | 29445955 | Точно: 5C, включая дубли |
| List response frames, включая missing | 481884 | Точно по chunk64, begin/end |
| Минимальные JSON bytes строк, первая итерация | **35335146** | Не менее 2C×3; каждый непустой JSON string ≥3 B |
| То же, две итерации | **88337865** | Не менее 5C×3; ещё без headers/requests/прочих журналов |
| Assume и distinct score calls | ≤99474 | Верхняя граница 2S; реальные число/траектория неизвестны |
| LM requests с close | ≤198949 | Верхняя граница 2/score+1 |
| LM lookups | ≤77191824 | Верхняя граница 776/score |
| LM response frames с close | ≤795793 | Верхняя граница 8/score+1 |
| Membership checks / одна segmentation | ≤101310 | Верхняя рекурсивная граница, не измеренный расход |
| Membership checks всего | ≤10077710940 | Грубый upper bound, не прогноз |

NoSpace-bound: `f(n)=1+Σ[l=1..min(n,46)](n-l+1)`; каждое успешное разбиение удаляет ≥1 знак. При монотонном f функция `B(n)=Σ[j=1..n]f(j)` удовлетворяет `B(a)+B(b)≤B(n−1)` для a+b≤n−1. Поэтому membership≤B(87)=101310. Пробелы после сегментации дают C_char≤173 и W≤87; Prefetch требует до262 unigram +514 higher-order lookup, 3+5 response frames. Ошибки/ранний STOP только уменьшают объём незавершённой попытки.

**Доказанное противоречие:** первая полная итерация требует минимум35335146 B одного real IPC JSONL. Это на26946538 B больше cap8MiB и на1780714 B больше total32MiB **ещё без остальных файлов**. Строки нельзя выкинуть как «неважные». При иной более ранней остановке первая итерация всё равно не завершена. Этот вывод не использует plaintext score или предполагаемый найденный ключ.

Остальные границы нельзя выдавать за необходимые фактические counts: upper bound выше512/20000 не доказывает, что именно этот контроль их превысит. Но старые caps не гарантируют завершимость; никаких увеличений здесь не сделано. Консервативный upper bound только list responses —1277800917 B (ASCII escaping + frame allowance), также не полный output budget. Полный peak Perl hashes/segmentation/tree и время87-search не установлены. 180s watchdog/AS64MiB могут остановить нагрузку; не доказывают, что она уложится, и не являются непрерывным cgroup/RSS bound.

## 5. Минимальное условие снятия и один будущий объединённый gate

**Нельзя выдавать текущий комплект за executable-ready.** Минимально требуется перспективное решение о хранении повторных list deliveries: либо lossless журнал с доказуемым bound (например, один byte-exact blob списка плюс все ordered reference events с возможностью восстановить полный поток), либо заранее обоснованный отдельный output/disk/IO budget. Это изменение инженерного evidence-формата, **не разрешение исключать полноту, дубли или raw-эквивалентность**. Простое поднятие512/20000 не устраняет доказанный output-блокер. Уменьшение pl/mi или выбор другого текста ради прохождения не предлагается.

После этого нужны обоснованные hard abort quotas для запросов/lookup/segmentation и общий memory/input-pages/output allowance при прежней conservative shared-cgroup формуле. AS/RSS нельзя оценить из числа байтов JSON. Если completion-bound остаётся слишком большим, заранее допустим только честный pilot с BUDGET_EXHAUSTED/INCOMPLETE, без утверждения о чувствительности/отрицательного результата контроля; его полезность и quotas должны быть зафиксированы **до** исполнения. В данной версии этого обоснования нет.

Один будущий пакет должен объединить (без микроперезапусков):
1. Только необходимые original-vs-adapted differential fixtures для нового transport/evidence и frequency entrypoint; zero score-bit tolerance, exact segmentation/ordered ties/keys/trajectory, negatives. Изменение init не сравнивать с прежним вручную заданным root как будто входы равны.
2. При выполнении gates — ровно один новый frozen ciphertext87; decoder не читает truth/source/key. Оригинальные initialization/arithmetic/order, две итерации; никаких дополнительных seeds/polish/target.
3. Все writers close → wait/terminal → consumed byte receipts → два hashes и немедленный raw tool stdout → неизменяемый manifest/result → архив → **exact fresh Library readback** до общего PASS. Полнота IPC и observations остаётся обязательной; исключений по неудобному файлу нет.
4. Отдельные исходы: output/CPU/request/time exhaustion = INCOMPLETE_BUDGET; exception/mismatch = STOP; unsafe/unconfirmed termination = UNKNOWN. Завершённый blind search с inverse87/87, но иной строкой = CONTROL_NOT_RECOVERED. Exact recovery отдельно, без объявления sensitivity. Доставка без exact readback = DELIVERY_UNVERIFIED; foreign run не повторяется.

Старые scientific T0 не менялись; новый scientific attempt не начинался. Source diffs: **нулевые**, сохранены reference copies для строк доказательства. В FREEZE_BLOCKED.json allowed_execution=[]; approval command отсутствует. Не предлагается ещё один запуск ради наблюдения заведомого output-cap.

