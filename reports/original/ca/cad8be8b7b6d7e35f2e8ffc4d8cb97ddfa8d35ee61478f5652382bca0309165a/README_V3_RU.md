# TS-RECOVERED-SEARCH-v3 — executable freeze для рассмотрения

**Подготовлен, не запущен. Разрешения на retry пока нет.** Предыдущая v2 STOP и delivery readback не изменены.

Новая директория: /workspace/scratch/f24f8fae4976/TS_RECOVERED_SEARCH_v3.
Активная команда записана в COMMAND.txt и FREEZE.json. Launcher берётся побайтно из v2, вычисляет R по своему расположению; attempt и launch_evidence.json в новой папке отсутствуют.

## Изменение
Ровно принятый ремонт: runtime/run_profile.py SHA256 3f0f5ce4c4e459670fbc52a39e7fd33a5e2e95239b1c22462458e2a232e6211c; добавлен runtime/limit_order.py SHA256 1474f2bbc8f42ae99c1c5612c95228fb3321b56b064cf0f2ff297decdaab60e3. Diff SHA256 cd17b6d853236ccf88e4b27da64d2bf29b07c80f2e49455900c261a87ae6be28. Обратный diff даёт точные исходные bytes supervisor. Остальной runtime и все sources неизменны.

Supervisor soft AS128 MiB с подготовки; hard AS временно256 MiB для наследования детьми, затем128 MiB до G. Итоговые AS128/128/256 MiB. Принятый собственный smoke — историческое finite evidence в history/limit_order_repair; здесь повторно не запускался.

Чтобы сохранить ровно проверенный патч, строка result.version внутри runtime/run_profile.py остаётся TS-RECOVERED-SEARCH-v2. Она не используется как идентификатор новой попытки: v3 определяется FREEZE/manifest/новым путём/launch receipt. Остальные документы v2 с прежними version labels сохранены как история; новый scope задаётся этим файлом и VERSION_TRANSITION.json.

## Неизменный исполнительный scope
Только Lincoln→Bedell87 blind MCTS: штатная initialization и максимум две полные Expansion с профилированием. Ни Dorabella, ни иных контролей. Истина/key доступны только post-terminal evaluator; ciphertext, truth, selection freeze, normalization, key/seed, original arithmetic/scorer/ordering/ties и все14 моделей/индексов побайтно прежние. Большие входы остаются в TS_RECOVERED_v2_data, не дублируются в ZIP и не перестраиваются; model_inputs.json задаёт точные absolute paths/bytes/SHA.

Python pinned3.12.14, -B -I -S; оригинальный Perl pinned5.38.2. MCTS -n -v -mi 2 -pc 1 -pl 50 -cc 0.05. PERL_HASH_SEED=2026101705; PERL_PERTURB_KEYS=0; LC_ALL=C; TZ=UTC.

Одна попытка после отдельного разрешения. 180s total от нового launcher T0, work cutoff130s; max3 процесса; AS128/128/256MiB; CPU supervisor170/175s, children120/125s; NOFILE64; CORE0; FSIZE8MiB; total audit96MiB. 1024scores, 2049LMrequests, 794624lookups, 200000membership, 212000pat sequence; frame65536B. Никакого retry/resume/tuning или переноса старого времени в новую разрешённую попытку без её явного учёта; старый T0/STOP хранится отдельно и не обнуляется.

Прежний ресурсный gate: max8GiB; current строго <5468942336B, без вычитания cache. Полная формула input_pages1376161792 + AS536870912 + allowance134217728, сумма с current <7516192768B. Новые metadata/helper помещаются в прежнюю input-page границу; она не повышена. Новая подготовка не является свежим admission будущего запуска. Launcher повторно проверяет identities, exact process guard и gates до release. В guard сохранены прежние пути и добавлены5 соответствующих путей v3.

Полнота двух Expansion, native best/recovery и inverse87/87 различаются. INCOMPLETE_BUDGET/STOP не означают отрицательную проверку метода. Технический smoke не доказывает search sensitivity или отсутствие иных runtime ошибок.

## Приёмка будущей попытки
Те же raw tool stdout computed hashes → закрытые файлы/seal → точный ZIP Library readback, fail closed. runtime/verify_delivery.py не изменён. При STOP не повторять. Последнее подтверждение scope должно указывать именно новый ZIP/FREEZE/MANIFEST и COMMAND.txt.

В этой подготовке только data-only hash/copy/ZIP и AST parsing; никаких imports/compile/run исправленного supervisor, broker, Perl, solver или smoke.
