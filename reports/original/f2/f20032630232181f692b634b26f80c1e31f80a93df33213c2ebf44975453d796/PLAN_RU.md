# Один минимальный дифференциальный oracle, prospective до исполнения

Разрешение: пользователь в текущем сообщении разрешил один заранее frozen малый
тест неизменённых уже approved Utils/NoSpace после PASS adapter-v2, если нет новых
permissions/dependencies/risks. Условия соблюдены: same pinned source commit,
Perl5.38.2/arch/env, два fixture, без MCTS/ReadLM/JMSmoothing/full model/target.
Исполнение нового modified solver/glue НЕ входит в этот план.

Собственный harness original_module_oracle.pl вызывает оригинальные функции; в
копию прежнего harness добавлена только runtime-guard Config до use Utils/NoSpace.
Исходники автора побайтово прежние. Core JSON::PP/Config не устанавливаются.
NoSpace use lib '../Modules' разрешается из новой пустой attempt/work; такого
Modules-каталога нет. -I указывает точное pinned original directory.

Вход1: golden fixture102байта,5 групп/16 кандидатов/9 слов/maxlen6/10 segmentation.
Вход2: source subset1960997байт,18307 строк;7 pattern (один absent),68945 кандидатов,
полный словарь123619,maxlen46,6 segmentation. Правило subset уже frozen до adapter
и не менялось: все original-order1, все строки7 patterns, первая строка maxlen46.
Полные списки и порядки, включая дубли; отсутствующая группа undef↔JSON null.

Критерий заранее: оба полных JSON-объекта точно равны expected, массивы строго
по порядку, словарь как отсортированное множество, maxlen как целое, строки
segmentation побайтово. Tolerance=0; никаких вероятностей/численных score здесь нет.
Harness сравнивает canonical JSON; собственный supervisor повторно читает сохранённый
stdout и сравнивает полные decoded structures без повторного вычисления функций.
Требуются ровно2 строки stdout, пустой stderr, normal exit0, terminal evidence.

Один author invocation с двумя fixture внутри, без retry/resume. Общий wall30с
от T0 supervisor включает hashes/подготовку/load/test/readback; при deadline TERM,
через2с KILL, это не гарантия realtime при остановке host. AS512MiB,CPU25/28с,
core0,nofile64,stdout/stderr regular files≤16MiB каждый. Входной cgroup gate8GiB,
current≤7GiB; stop при наблюдении≥7.5GiB. Нет установки/изменения security/network.
Размер данных<2MiB, expected3.16MiB; исходная full7табличная модель не загружается.
AS — физически применяемый ограничитель process allocations, не резерв общей RAM.

Собственный stdlib child_gate входит в отдельную session/process group, применяет
лимиты, записывает ready и ждёт один GO. Родитель до GO проверяет PID namespace,
NSpid/NSpgid/NSsid, visible/local PID, parent и starttime; NamespaceView скопирован
без изменения из исправленного собственного TS-RC-v2 supervisor. GO разрешает
один os.execve Perl с фиксированными argv/env. Оригинальный код не форкается.
Возможные сигналы адресуются только доказанно своей группе. Нет hostPID=localPID
предположения. stdout/stderr caps обеспечены regular files+RLIMIT_FSIZE, не pipe.
EOF gate до GO прекращает child без author exec. Неясное управление/остаток группы
означает STOP/UNKNOWN; никакого запуска замены.

При PASS: PASS_ORIGINAL_MODULE_FIXTURES_ONLY. Это проверенная эквивалентность
конкретных списков/словаря/16 результатов NoSpace; не общее доказательство,
не численная эквивалентность scorer, не готовый native bridge и не test sensitivity.
Полный solver, поиск, counts/seeds/Dorabella не запускать после результата.
