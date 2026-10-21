# TS-JOURNAL-DIAGNOSTIC-v1 — один prospective диагностический запуск

Статус: **PREPARED_NOT_EXECUTED; требуется согласование этого пакета**. T0 отсутствует. Старые failure bundle, native PASS и independent STOP неизменны. Никакой 87-control, target, scorer, solver или новой криптоаналитической серии.

## Зачем именно этот scope

Единственная будущая попытка повторяет только фиксированный real transport исходного TS-COMBINED-STORAGE-v1 с наблюдением journal. Synthetic MCTS повторно не запускается: его 320 совпавших событий и прежний PASS проверяются как закреплённые данные. Все real inputs и порядок прежние: 8 list-fetches (`a,aa,ab,aba,abc,abcdefgh,!,abcdefgh`), 9 LM batches (36 и восемь по 776), 6244 lookups, 132856 candidate occurrences, те же 6 NoSpace examples, 35 membership queries и закрытия. Никаких дополнительных запросов к модели, новых текстов или подбора параметров.

Это минимальный неизменённый real workload, внутри которого произошёл обрыв. Сокращение списка/числа LM batches устранило бы воспроизведение исходного порядка и последней границы. Дополнительное I/O-инструментирование меняет timing, поэтому даже полный успех новой попытки не устанавливает старую причину. Это диагностический шаг, не переименование прежнего full gate в PASS.

## Старый verifier: наблюдение и вывод

`prior_evidence/stage_real.json`, поле `result.json:stages.real` и raw stdout содержат один и тот же сериализованный объект `PASS_FINITE_COMBINED_TRANSPORT`: LM requests/frames 10/58, pat 45/2131, LM6244, candidates132856, сегментаций6. Это фактически сохранённые значения. По `baseline/run.py:161,163` они должны происходить из возврата `real()`. Отдельного наблюдения вызова, загруженного code object или hash потреблённых байтов нет. Поэтому нельзя заявить, что непосредственно удостоверено принятие именно нынешнего неполного файла. `OLD_VERIFIER_EVIDENCE.json` отделяет эти утверждения.

## Изменения и неизменные части

`broker.py` отличается от baseline только импортом `Journal` и заменой конструктора log. Прежние response bytes, порядок запросов/списков, дубли, кэш, segmentation, unknown/missing, Perl arithmetic и критерии `readback.real()` не изменены. `transport_probe.pl`, `Prefetch.pm`, `CompactPatList.pm`, original modules, lookup-код, данные и `readback.py` побайтово прежние.

Новые `evidence_io.py` и `verifier_binding.py` — диагностические I/O-компоненты. Точная прежняя source-версия `readback.py` проверяется по SHA и загружается из этих байтов, без чтения cached pyc. Только его функции чтения `iter_rows/load` заменяются наблюдаемыми эквивалентами для фиксированных UTF-8 JSON; `real/ipc/need` и сравнения не переписываются. Эти изменения требуют будущего согласия; сейчас не исполнялись, в том числе compile/import.

## Одна последовательность, без retry/resume

1. `launch.py` отказывает при существующем attempt/launch marker; фиксирует отдельный диагностический T0 до подготовки и exec-ит supervisor. Hash/runtime/14-model identities и prior/live-process guard проверяются до broker/Perl. Старый научный T0 не изменяется.
2. Прежний initial admission: memory.max=8589934592 B и **memory.current < 5877698560 B**, без вычитания cache. Сохраняются последующие post-hash/shared-memory gates. Если нет допуска — NO_GO/SKIPPED_RESOURCE, без обхода.
3. Ровно одна real-пара: один broker и неизменённый Perl transport. Journal остаётся buffered `xb`; fsync к нему не добавляется. Перед write сохраняется INTENT/hash; после flush фиксируются write-return, fd/path dev/inode/size, offset и прочитанные через отдельный readonly fd байты. Они обязаны совпасть с намерением. После close полный read того же inode сравнивается с накопительными hashes; только затем writer completion.
4. Supervisor ждёт оба exit 0/пустые группы и сохраняет `wait_before_verifier.json`. После wait вызывает исходный verifier и отдельно сохраняет **фактический return или exception**, source/code hashes, path/identity/размер/hash всех потреблённых файлов и EOF.
5. Final binding требует writer completion, ровно 2244 IPC-records, два close по старому verifier, неизменность dev/inode/size/hash между writer/readback/seal, правильный monotonic порядок close→completion→wait→verifier. Повторное чтение при publication должно совпасть с сохранёнными hashes. Любое расхождение — STOP. Никаких недостающих записей из counters не достраивается.

## Прежние бюджеты и риски

Один global180s от T0, preflight≤90s, real+readback+rehash≤60s, прежние real-probe≤30s и LM≤10s, cleanup reserve4s. До3 одновременных процессов включая supervisor; только2 child invocations. AS64MiB каждому; small CPU45/50s, supervisor170/175s; NOFILE64, CORE0, FSIZE8MiB, суммарный output32MiB. Hash order/env неизменны: `PERL_HASH_SEED=2026101705`, `PERL_PERTURB_KEYS=0`, LC_ALL=C, TZ=UTC. Нет сетевого кода, установки или новых зависимостей.

Resource formula прежняя: 1370058752 B входных страниц + 201326592 B process AS + 67108864 B allowance; shared abort7516192768 B и номинальный reserve1GiB. Это не reservation общей памяти. Текущий admission не заявляется — свежий снимок обязателен при будущем запуске. Большие входы сейчас не перечитывались и не перестраивались.

Дополнительные handles: journal observer fd и audit fd; исходные pipe ends не меняются. Audit пишет потоково, без накопления records. Для2244 событий максимум INTENT512 + AFTER_FLUSH1024 + WRITE_FLUSH_READ1024 B на событие, OPEN/CLOSE по2048: ≤5748736 B, ниже прежних8MiB/file; превышение любого собственного bound — STOP. Предыдущие raw outputs около4MiB; добавочные receipts и static inputs помещаются в прежний32MiB output/64MiB allowance, без его повышения. Запросы/списки не накапливаются дополнительно. Это статические ограничения, не измеренный peak новой версии; AS и shared-memory gates остаются обязательными.

Наблюдение добавляет syscalls/чтения и может изменить timing; может вызвать STOP по прежнему сроку. Deadline кооперативный с наблюдением и group cleanup, не обещание realtime kill при host failure/непрерываемом I/O. Fsync receipt/atomic replace не гарантируют durability после host-crash; directory fsync не добавлен. Нет гарантии против согласованной внешней подмены всех свидетельств.

## Как различаются наблюдаемые неисправности

| Наблюдение | Установимый вывод |
|---|---|
| INTENT есть, последующего подтверждения write/flush/read или completion нет | Незавершённая/неудостоверенная запись на указанной фазе; причина только по сохранённой ошибке, отсутствие receipt само по себе не доказывает buffering |
| После flush read через отдельный fd не равен записанным bytes | Несоответствие видимых файловых байтов в этой точке; не автоматическое определение виновного компонента |
| fd сохраняет inode, path указывает на другой либо исчез | Замена/исчезновение path обнаружены; субъект и механизм замены не устанавливаются |
| inode прежний, размер/hash между фазами изменились | Изменение содержимого/размера между наблюдениями; snapshot не устанавливает все промежуточные операции |
| Writer/read hashes совпадают, исходный verifier raises | Прежний критерий отверг эти bytes; записывается точное исключение, PASS запрещён |
| Verifier return PASS, но его consumed hash отличается от final seal | Прямо установлен разрыв verifier→seal, STOP |
| Все identities/hashes/EOF/counts/close/wait совпали | Только `PASS_DIAGNOSTIC_THIS_ATTEMPT_ONLY`; старая причина остаётся неизвестной, старый STOP не отменяется |

## Команда и доставка evidence после будущего согласия

Единственный вход: `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -B -I -S /workspace/scratch/f24f8fae4976/TS_JOURNAL_DIAGNOSTIC_v1/launch.py`.

Наблюдать только эту session до terminal; сохранять raw command/tool receipt, stdout/stderr, phases/limits/process identities, writer events/completion, verifier return/exception/read hashes, seal observations/binding и final result. После exit — независимый data-only readback тех же сохранённых файлов/хешей и полный archive; это не повтор workload. Любой UNKNOWN/STOP/сбой — остановка без правок или повторов. Полный gate принимается только при согласии raw exit/cleanup и конечного независимого readback. Запуск 87-control/target этим scope не разрешается.
