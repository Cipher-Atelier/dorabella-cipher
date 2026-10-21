# BE-W16-v1 — подготовка единственного пилота

Статус: **PREPARED_FOR_EXTERNAL_READBACK, NOT_EXECUTED**. Готовность файлов не означает проверенную runtime-эквивалентность. Исходная спецификация `protocol.md` сохранена буквально; её прежняя метка SPECIFICATION_ONLY относится к моменту её создания. Новое исполнение требует согласования именно этого пакета.

## Входы и предел независимости

Материализованы ровно P1–P4/N1–N4 из ранее сохранённых capture, без новых источников, замены строк, отбора по словарю или score. Собственная data-only попытка завершилась `PASS_INPUT_DATA_ONLY`: восемь длин 87, четыре положительных inverse 87/87, четыре inverse перестановок negatives, отсутствие точного совпадения с двенадцатью перечисленными сохранёнными inventories. Это проверенная свежесть относительно этих inventories, **не** доказательство отсутствия текстов в обучающем корпусе или всей исторической работе. Отрицательная строка имеет обратимую генерацию; это не recovery.

Decoder получает только отдельный JSON `{id,ciphertext}`. Truth, источники, ключи и negative permutation сохраняются отдельно; supervisor проверяет их hashes при подготовке, но разбирает truth только после закрытия всех дочерних поисков. Отсутствие случайной передачи в argv/IPC проверяется по коду; OS-секретность от собственного supervisor не заявляется.

## Исполняемые границы

**Неизменные сторонние файлы:** `runtime/original/JMSmoothing.pm`, `NoSpace.pm`, `Utils.pm`, `FreqAnalysis.pm`; дополнительно `ReadLM.pm` нужен только для исходного oracle на малых fixtures. Их bytes сопоставлены с pinned HHK commit `2c7ad49cd4f4fa852168a8ce295bf739bf076adc` через сохранённый original и SOURCE_PROVENANCE. Полный исходный MCTS не запускается.

**Авторский производный код:** `runtime/BEOps.pm` — новое имя package и `our @C`, но тело `Assume` буквально равно byte interval 13349:14523 исходного `masc_solver_mcts.pl`, SHA тела `ed73bec2471ab88ac2a34b207314d16671b311c27910b7016ee2fb9219542ee9`. Этот файл не называется полностью собственной реализацией.

**Новый собственный executable content:** `launch.py`, `supervisor.py`, `child_gate.py`, `common.py`, `store.py`, `broker.py`, `driver.pl`, `readback.py`, `delivery_readback.py`. `driver.pl` — собственная orchestration и storage glue, исполняющая перечисленные авторские модули и `Assume`; поэтому разрешение на прежние fixture-запуски не покрывает этот поиск автоматически. Python `readback` проверяет сохранённые данные, mapping, порядок и segmentation trace; Python не вычисляет языковые scores. Декодирование для verifier является проверкой сохранённого ключа, не поиском.

**Повторно используемый собственный код без изменений:** namespace_view, process_guard, limit_order, disk_contract в `runtime/reused`. Все компоненты и fixtures перечислены в manifest. `process_guard_cases.json` — ранее сохранённые данные, новые smoke не выполнялись.

## Статическое соответствие

* Исходный frequency order взят из original строки 37: `e t a o i n s r h l d c p u m f g y w b v k x j z q`; вызовы FreqAnalysis сохранены. Hash ties внутри оригинальной функции не заменены лексикографическими. Перспективно фиксированы PERL_HASH_SEED=2026101705, PERL_PERTURB_KEYS=0.
* `driver.pl`: root оценивается первым; восемь полных обходов start=0..85 × requested length=2..46; исходное усечение substr на конце. Квантиль floor((2r+1)L/16), L≤50, 16 bins, SHA priority и tie `(s,l,j)` зафиксированы. У текущего key одна неизменная копия на весь раунд. Межbin дубли удаляются по меньшему bin, без refill.
* Оценки идут по bin; следующий current — лучший новый ребёнок даже при ухудшении. Numeric ties: полная plaintext ASCII, затем key. Пустой раунд не меняет current. Partial round не меняет состояние. Global best отдельно, все максимальные различные 87-строки сохранены. Seen — наличие key, score=0 не считается missing.
* NoSpace исполняется исходным Perl. До него загружается exact presence всех подстрок; tied FETCH возвращает 1/undef, считает каждый logical call и записывает его ordinal, включая false/repeats. Незагруженный ключ STOP. Источником является исходный order-1 словарь, не объединение всех patlst строк.
* Prefix не сортируется и не deduplicate: source segments в seq order, первые 50, восемь нужных квантилей. Readback использует другой parser и сопоставляет source bytes, reference order и raw frames.
* Raw numerical strings поступают в обычные Perl hashes; unknown replacement, backoff, rounding и арифметика — неизменный JMSmoothing. Prefetch сам ничего не округляет. Scored results сохраняют `pack('d<')` bits; Python сравнивает уже сохранённые конечные IEEE-double значения, не воспроизводит scoring.
* Новый verifier проверяет все окна, квантиль, последовательность mapping replacements/swaps, выбор bins, ключи, transitions, ties и 87 позиционных inverse. Частота и tie order original initialization записываются; совпадение hash iteration с другой реализацией не заявляется.

## Единственный будущий запуск

T0 записывается до identity/resource/fixture gates. Общая подготовка ≤60 s, включая hashes и два малых интеграционных набора: prefix order/duplicates, bulk membership/NoSpace exact segmentation; original full fixture LM против нового prefetch — raw strings, 0/00/0.00, missing/unknown, backoff и score bits/error class. Только exact PASS обоих допускает восемь поисков. Это интеграционные проверки новых соединений, а не повтор старой калибровки.

Все восемь входов последовательно, новый холодный broker/Perl на каждый; 180 s/case, work cutoff130; до 129 scores, восьми раундов. Общий предел 1500 s. Никаких retries/resume, target, сети, установки или полного MCTS. Недостаток времени/памяти/лимита → INCOMPLETE/STOP, не замена входа. При INCOMPLETE с подтверждённым cleanup следующий заранее назначенный вход сохраняет собственный бюджет; correctness/resource/unknown прекращает дальнейший запуск, остальные NOT_STARTED.

GO остаётся: все восемь complete + ≥3/4 unique exact recovery + четыре строгих positive-best > negative-best; tie не считается recovery/строгим превышением. Любой иной исход NO_GO этой версии. Это малый pilot и описательный discrimination gate, не p-value и не гарантия чувствительности к Dorabella/CH1 B1–B3. Никакого автоматического target.

## Ресурсы и риски

На случай прежние перспективные caps: 30960 windows; 13068990 logical membership; 493812 physical word lookups/3870 batches; 100104 LM lookups/258 content requests+close; 3870 prefix requests; prefix source64MiB; frame65536 B; source row118052 B; evidence96MiB, отдельные файлы8MiB. Числа — верхние границы/stop caps, не ожидаемое фактическое время.

До release max3 процесса: supervisor/broker/Perl с эффективными AS128/128/256MiB, CPU170/175 supervisor (вся сессия),120/125 children, CORE0, NOFILE64, FSIZE8MiB. Исправленный limit_order сохраняет **soft AS supervisor128MiB**, временный hard ceiling256MiB до создания последней пары; иначе следующий Perl не смог бы унаследовать256MiB. После последнего child hard supervisor запечатывается128MiB. Это явно описанный порядок наследования, не увеличение effective parent AS. AS — виртуальное адресное пространство, не RSS.

Admission неизменен: memory.max8GiB, memory.current<5468942336; без вычитания cache; input pages1376161792, AS536870912, allowance134217728, monitoring до7GiB. Gates свежие перед каждым случаем/release. Input identities полностью hash-проверяются один раз в общих60s, далее stat identity до/после случаев; это не защита от враждебной незаметной перезаписи с восстановленным mtime.

OS AS/CPU/FSIZE ограничивают отдельные процессы; wallclock, aggregate evidence и shared-cgroup наблюдаются supervisor. Это не гарантия realtime deadline/атомарного group disk cap/host-crash durability. Наблюдатель может обнаружить превышение после последней записи; такой случай fail-closed, не PASS. Cache не считается гарантированно освобождаемым. При непредвиденном потомке/namespace mismatch STOP; сигналы только группам с установленными PID/NSpid/starttime/PGID и происхождением. Хостовый SIGKILL/crash может оставить UNKNOWN — отсутствие ответа не означает termination.

Одновременно только bounded substring table≤3828 keys, prefix cache восьми элементов на pattern, LM LRU4096, один frame/row, SQLite cache4MiB/mmap0. Raw sizes не выданы за измеренный Perl heap. Объектный peak, throughput и завершимость за130s **не доказаны**; новый код, включая Perl syntax/runtime, пока не исполнялся.

## Evidence и prospective приёмка

Broker сохраняет каждый фактический request/response frame; consumer независимо считает тот же stream hash/count/order. Membership references reconstruct exact keys по каталогу подстрок; data readback сравнивает каждое значение с индексом и каждый logical ordinal с исходным NoSpace control flow. Нет замены полного сравнения одним hash.

После wait/пустых собственных групп закрываются writer streams; raw outputs, result/readback и файлы запечатываются без self-append. Первичный tool stdout получает вычисленные case/root seal hashes. Финальный GO возможен только после точного ZIP Library readback и сопоставления с этим raw stdout; `delivery_readback.py` выполняет лишь data-only проверку. Сам upload/readback не входит в сеть вычислительных процессов и не является разрешением расширить поиск. При потере первичного tool stdout — недостающая delivery evidence, не восстановление по тексту модели. Исторические STOP не меняются.

Нынешние свидетельства: успешная отдельная own data-only материализация; source/hash comparison; AST parsing собственных Python без import; ручной статический review Perl. **Нет** выполненного нового поиска, Perl compile/import, runtime differential PASS или recovery outcome.
