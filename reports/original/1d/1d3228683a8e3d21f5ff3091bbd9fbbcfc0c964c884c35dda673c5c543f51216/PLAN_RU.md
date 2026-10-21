# TS-DIFF-BRIDGE-v1 — только малый differential, ожидает одобрения

Состояние: PREPARED_NOT_EXECUTED. Новый Perl glue, harness, broker и supervisor
не запускались; `perl -c` и imports нового кода не выполнялись. Старые результаты
Storage-v2, adapter-v1 STOP, adapter-v2 и original-oracle не изменены.

## Конкретный следующий шаг

Одна попытка `run_differential.py` после отдельного подтверждения владельца.
Сначала неизменённые оригинальные модули и оригинальные вычислительные функции
работают с маленьким обычным Perl-хешем; затем те же функции — с tied hash,
получающим списки/членство от Python readonly adapter-v2. Сравниваются целиком
два упорядоченных потока результатов. Ни один этап не читает Dorabella, полный
индекс 537 MB или исходную полную модель. Никакого retry/resume.

Одобрение относится только к этой fixture-проверке. Файл
`masc_solver_mcts.compact.pl` — точный предложенный production diff, но его
запуск, полная модель и технический 87-control в это одобрение НЕ входят.

## Исходники и минимальная интеграция

Pinned upstream: bmhauer/hhk-decipherment,
commit `2c7ad49cd4f4fa852168a8ce295bf739bf076adc`.
Прямой источник: https://github.com/bmhauer/hhk-decipherment/tree/2c7ad49cd4f4fa852168a8ce295bf739bf076adc
Это локальная проверка уже закреплённых исходников, не новый fetch сайта.
Авторство: Bradley Hauer, Ryan Hayward, Grzegorz Kondrak,
*Solving Substitution Ciphers with Combined Language Models*, COLING 2014.
Оригинал и производные распространяются с указанным авторством под CC BY-SA 4.0;
исходный LICENCE включён.

`MINIMAL_INTEGRATION.diff`: добавить модуль CompactPatList, заменить только
ReadPList (original line 106) на attach для режима -n, закрыть IPC после stdin-loop.
Хвост original lines 154–540, включая все функции поиска, побайтно неизменён.
Это не обещание полной эквивалентности исполнения.

Harness `differential.pl` использует original lines 154–535; семь строк
OBSERVE_ONLY добавляют журналирование. После их удаления исходный блок совпадает
побайтно. Изменён startup: фиксированные fixtures/ключи вместо CLI/stdin/частотной
инициализации, нет shell `date`, времени в trace и target. Обе стороны используют
ОДИН harness. ReadLM/JMSmoothing/Utils/NoSpace — неизменённые копии модулей.
Оригинальная ProbCharWord вызывается через наблюдающую оболочку, с исходными
аргументами и возвращаемым значением. `FreqAnalysis` здесь не вызывается.

## Контракт хранения и затронутая семантика

* FETCH pattern: полный новый arrayref либо undef, порядок source seq и дубли
  сохраняются; higher-order hashes пусты, как у -n. Никакой предварительной
  сортировки, дедупликации, top-k, численного преобразования или score-cache.
* FETCH word: 1/undef только по исходным order-1 словам; не по всем слитым
  кандидатам. maxlen — исходный максимум после -n. NoSpace остаётся исходным
  longest-first/leftmost recursive алгоритмом, не Viterbi.
* Tie hash запрещает запись и перечисление. В рассматриваемом -n call path
  исходный код требует только чтения ключей, что видно в original 406–465 и
  NoSpace 9–36. Это узкий API, не универсальная замена Perl hash.
* Python adapter.py побайтно равен прошедшему adapter-v2. Его LRU: 2 списочных
  записи/8 MiB учтённого payload, 1024 membership-записи, свежие копии списков.
  Лимит payload не заявляется как весь RSS. SQLite URI mode=ro + query_only;
  соединение и source закрываются в finally. Пересборки индекса нет.
* IPC: два безымянных pipe, ASCII JSON lines, последовательные request IDs,
  op meta/list/word/close; probabilities/scores/keys через IPC не передаются.
  65,536 bytes на frame, 80,000 requests, без fallback. Это fixture-bound мост:
  нынешний frame cap НЕ аттестован для самых больших списков полной модели.
* ReadLM хранит исходные probability strings; умножение, log, суммирование,
  округление, truthiness нулей и unknown replacement выполняет оригинальный Perl.
  В JSON результата пишутся %.17g и hex `pack('d<')`; требуется Perl NV double/8.
* Строгое `>` и stable similarity-sort сохранены. `keys %newkeyhash` не заменено
  сортировкой. Дополнительные allocation/IPC теоретически могут повлиять на
  наблюдаемое tie/hash поведение: это причина точного сравнения, не допущение
  эквивалентности. Hash-order mismatch = STOP, а не выбор другого seed.

## Фиксированные входы, бюджет работы и критерий

`fixtures/fixture.patlst` (102 bytes) и `fixture.sqlite` (20,480 bytes) скопированы
из завершённого adapter-v2; это golden fixture, не новый full build. 7 строк,
5 групп, 16 candidate occurrences, 9 исходных слов, maxlen=6. Хеши — в manifest.
Шесть малых численных таблиц — явно синтетические значения, перечисленные целиком
в fixtures/char.1–3 и word.1–3. Это тест арифметического контракта, не обученная
LM и не проверка качества декодирования. Есть last-write duplicate `cat`,
truthiness-zero `zz`, неизвестное слово и пустая строка. Точные значения заданы
до результата; численные ожидаемые scores сейчас не рассчитывались.

Три одинаковых для двух сторон случая:

| case | ciphertext | C, порядок слотов | root |
|---|---|---|---|
| C1 | abcabc | a,b,c | cat |
| C2 | abcabc | a,b,c | dog |
| C3 | ababab | a,b | to |

Каждый: -n semantics, mi=2, pc=1, pl=50, cc=.05, ngramorder=3,
исходные шесть lambda-констант. Оба режима отбора кандидатов посещаются:
iteration 1 — source order, iteration 2 — stable similarity order.
Тексты и ключи специально малы; это 6/6 roundtrip, НЕ 87/87 и не solver sensitivity.
Проверяется каждый root, каждый допущенный candidate key и child, каждый winner;
сохраняются все позиции, ключи, сегментации, scores и порядок.

На сторону ровно 6 MCTS iterations. Консервативный предел candidate visits:
3 cases × 2 iterations × 5 starts × 5 lengths × 7 candidates = 1050.
Исходный необычный bound `len <= length(ctext)+sta` сохраняется; substr может
укоротиться. Не более 1050 новых scored texts плюс 8 прямых probes; защитный
cap scorer calls 2200 на сторону, trace 20,000 событий, IPC 80,000 requests.
Caps останавливают с STOP, не обрезают научно учитываемый результат.

PASS_FINITE_DIFFERENTIAL_ONLY требует одновременно:
1. Нормальный exit0 reference, adapted и broker; пустые подтверждённые группы,
   пустой stderr, deadline соблюдён, hashes до/после совпали.
2. Полное побайтное равенство JSONL потоков; score tolerance = 0, включая все
   64 бита NV. Все segmentation/candidate/child/selection/iteration/winner traces
   совпали; никакой перестановки журналов для получения равенства.
3. Golden списки/дубли, absent key, original-order1 membership и 8 заранее известных
   сегментаций совпали с записанным oracle. Direct cat/dog score tie сохранился.
4. Ровно 3 winners и 6 iterations на сторону, наблюдены оба режима candidate order,
   полный inverse каждого сохранённого результата, штатный close IPC.

Любой mismatch, исключение, незавершённость, недостаточное покрытие или превышение
лимита = STOP/INCOMPLETE/UNKNOWN. Никакого повторного запуска или изменения fixtures.

## Реальное исполнение после одобрения

Entry command (cwd несущественен):
`/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -I -S /workspace/scratch/f24f8fae4976/TS_DIFF_BRIDGE_v1/run_differential.py`

Один supervisor; сначала один direct child gate→Perl reference, затем одновременно
два direct children gate→Python broker и gate→Perl adapted. Каждому своя session/PGID;
gate exec заменяет процесс, не создаёт дополнительный. Максимум 3 своих живых
процесса одновременно с supervisor, 3 child exec за попытку. Perl никого не порождает.
Числа FD выдаёт OS и receipt сохраняет фактические argv; иных аргументов нет:
* Perl: `/usr/bin/perl -I PACKAGE/original -I PACKAGE PACKAGE/differential.pl reference PACKAGE/fixtures`;
* Perl adapted: то же, `adapted PACKAGE/fixtures READ_FD WRITE_FD`;
* broker: pinned Python `-I -S PACKAGE/broker.py`.

Environment ровно PATH=/usr/bin:/bin, LC_ALL=C, TZ=UTC,
PERL_HASH_SEED=2026101705, PERL_PERTURB_KEYS=0. srand/rand отсутствуют;
seed здесь управляет Perl hash order, не случайным поиском.
Python 3.12.14/sqlite3 3.53.1; Perl 5.38.2 x86_64-linux-gnu-thread-multi/NV double8.
Только существующая stdlib/core: sqlite3, JSON::PP, Config, IO::Handle, sort и
прикреплённые исходники. Ни DBI, ни DBD::SQLite, ни pip/cpan/install, ни сеть.

Один общий 60s wall deadline с T0 до hash/preflight/load/reference/adapted/readback;
не по 60s на сторону. После deadline только termination/receipt, общая TERM grace
2s и KILL observation 2s. Это внешний watchdog с планировочными задержками,
не hard realtime. Каждому ребёнку AS=128 MiB, CPU soft/hard=20/22s, FSIZE=8 MiB,
CORE=0, NOFILE=32. Supervisor AS=128 MiB, CPU=30/32s, FSIZE=8 MiB, CORE=0, NOFILE=64.
Теоретическая сумма собственных AS не более 384 MiB при двух детях; это не cgroup
reservation и не оценка RAM полного solver. Малые fixtures всего ~23 KB,
теоретический tree/work bound указан выше; прежний большой oracle имел RSS~87 MiB,
но его нельзя использовать как доказательство RAM всех будущих входов.

Свежий gate: cgroup memory.max ровно 8 GiB и memory.current <=7 GiB; STOP при >=7.5 GiB.
Мониторинг ~50ms, не гарантия исключения внешнего OOM. Process-count ограничение
контролируется supervisor и статическим отсутствием fork/exec в разрешённых детях;
это НЕ kernel cgroup pids limit/RLIMIT_NPROC promise. PID/NSpid/PGID/SID/starttime
проверяются прежним namespace_view; сигналы только собственным доказанным группам.
При невозможности доказать адресацию STOP без release. Неизвестный исход не PASS.

`attempt` существует → отказ; matching live process → отказ; никакой новой распаковки
ради retry. Создание attempt/T0 не меняет старые scientific T0. Все stdout/stderr,
IPC request/response, ready/limits, /proc/cgroup наблюдения, exits, hashes и сравнение
сохраняются. Внешний raw tool receipt нужно сохранить отдельно без повтора процедур.
Хостовый crash может оставить неполный журнал; fsync/rename не является обещанием
долговечности scratch. Никаких самоперезапусков или очередей.

## Что будет и не будет доказано

Статически: неизменность арифметических функций и их порядка операций;
отсутствие чисел модели в IPC; отсутствие изменения candidate order в glue;
явно ограниченный readonly API. Следствие условно: при тех же аргументах и том же
runtime те же функции вычисляют то же; тест проверит, действительно ли storage
подаёт те же аргументы на этих случаях.

Только finite evidence: битовое равенство конкретных scores/траекторий, сегментации,
hash/tie-поведения с одной конфигурацией и этих toy inputs. Возможна общая ошибка
в обеих версиях оригинального алгоритма; сравнение не доказывает его математическую
корректность. Прежние oracle/golden checks дают отдельную проверку части контракта.
Не проверены полный model-load, все редкие patterns, большие IPC payloads, RAM и
скорость полного поиска, crash safety, иная платформа/Perl, начальная частотная
сортировка, 87-control, CH1 encoder или target. Для их допуска нужны отдельное
решение и измеренный ресурсный bound, не автоматическое продолжение после PASS.
