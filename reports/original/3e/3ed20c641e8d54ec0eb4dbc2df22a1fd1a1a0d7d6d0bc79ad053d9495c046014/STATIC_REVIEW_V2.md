# TS-RC-v2: исправление только supervisor, до единственного исполнения

Основание: пользователь разрешил исправить PID/NSpid/PGID/starttime, доказать управление собственной группой и затем выполнить один новый вызов с прежними научными объектами и ограничениями. TS-RC-v1/его ZIP не меняются.

Свежее независимое чтение 2026-10-17 11:59:12 UTC: совпадающих процессов нет; старых PID5438/5439 нет; старый рабочий root и новый v2-root отсутствуют. ZIP v1 SHA256 2fee72fe68b783884528a74771c60f9c3b9b92e959938d3a3315c2da97c80df8. Полный сырой /proc статус находится в independent_absence.json.

## Исправление адресации

NamespaceView получает proc-visible self через /proc/self, проверяет inode текущего PID namespace и pid_for_children, сопоставляет NSpid/NSpgid/NSsid с getpid/getpgrp/getsid. Для процессов того же namespace используется проверенная глубина вектора; принадлежность другому/непрочитанному namespace не даёт права посылать ему сигнал. Нельзя подставлять последний произвольный NSpid без проверки namespace. В статусах хранятся оба набора ID.

proc(local_pid) разрешает ровно одну соответствующую запись; пути /proc используют только visible_pid. Статус сверяется со stat до/после чтения, starttime защищает от reuse. Смена parent/group во время чтения делает текущий образец непригодным, а не основанием для сигнала. Собственная запись исключается по visible_pid+starttime; предки сохраняются отдельной цепочкой видимых PPID. Совпадающие посторонние runner/Perl не исключаются по совпадению числового локального PID.

До каждого exec короткий stdlib gate того же PID ждёт отдельный одноразовый pipe. Supervisor сначала удостоверяет local→visible PID, starttime, namespace, direct PPID и унаследованную группу. Затем gate делает execve точной GNUtimeout+env+prlimit+Perl команды. Это не новый алгоритм/Perl-вызов и не чтение контрольного stdin. Без разрешающего байта gate выходит без exec.

После GNUtimeout подтверждаются одновременно local PGID=local child PID, visible PGID=visible child PID и getpgid(local PID). Группа отлична от supervisor. Каждый член должен иметь подтверждённое происхождение от закреплённого anchor или ранее наблюдённую пару visible_pid/starttime; собственный процесс/предки/чужой namespace запрещены. Все killpg и Popen signals адресуются **локальными** ID; /proc limits/RSS/HWM — видимыми. Зомби не скрываются как исчезнувшие. После wait требуются два пустых просмотра группы с интервалом0.1s; неопределённость даёт STOP/UNKNOWN, не повтор.

## Ограниченная проверка управления — внутри того же 180-s попытки

До любого Perl выполняется ровно один собственный stdlib probe: GNUtimeout + те же env/prlimit, Python parent и один Python leaf в одной группе. Предел5s (из180), естественный сон10s не достигается штатно. Parent публикует локальные PID. Supervisor должен удостоверить все три процесса (watchdog/parent/leaf), послать TERM только этой группе; parent reaps leaf с exit−15 и публикует PROBE_REAPED, затем выходит. Только подтверждённые wait/отсутствие всей группы разрешают runtime Perl. Нет криптографических входов, scorer или проверки языка. SIGKILL через2s остаётся аварийным путём; успешный TERM-probe не объявляется динамической проверкой всех возможных аварий.

Проверка входит в общий T0→180s, не прибавляет отдельный бюджет. T0 начинается при входе main перед hash/extract/probe/runtime. Подготовка реализации/статическое чтение предшествуют попытке. Данные/model/cwd сохраняют **точные пути v1 из argv** (они ещё не существовали); новый attempt находится отдельно в TREESEARCH_first_control_v2/attempt. Старый manifest не изменяется.

## Что сохранено буквально

AST-сопоставление v1/v2 без импорта подтверждает тождество функций control, verify_result, prepare, limits_ok, resource_gate, tick. Значит, не изменены контроль/encoder/inverse, критерии recovery, загрузка7 TAR members с хешами, source/system hash-проверки, resource gate и global deadline. author_argv и runtime_probe_argv читаются из исходного manifest только после проверки его SHA256 7a713995f66a6f7fa0d66269b60e3bfab71ccaccf8dacd736172ec4d19937940. MCTS -n -v -mi2 -pc1 -pl50 -cc0.05, hash seed/order, модели и коэффициенты не меняются.

Остаются AS4GiB, CPU150:152, core0/nofile64/fsize16MiB, runtime≤5s, model-load≤60s, control≤120s и общий≤180s. Model-load отсчитывается консервативно от запуска собственного gate перед Perl. Никаких новых security/network settings, пакетов, target, retry/resume. Перед автором снова свежий resource gate.

Статическое чтение не подменяет динамический probe: до его фактического результата корректность управления условна. Не обещаются real-time/host-crash/cgroup tree isolation. Требование доказать прекращение относится к наблюдённой собственной группе в этом вызове; отсутствие чужих процессов не заменяет его.
