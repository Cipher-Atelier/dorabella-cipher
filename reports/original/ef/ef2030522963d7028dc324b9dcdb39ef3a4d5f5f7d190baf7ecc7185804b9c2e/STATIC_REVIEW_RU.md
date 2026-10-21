# Статическая сверка до smoke

Проверены64 члена первоначального MANIFEST. Старые bytes не изменены.
Новая копия broker отличается только подключением writer (import/constructor),
непроводным параметром send(final=False) и закрытием последнего chunk перед
отправкой уже существующего closed-response. Обратная замена пяти текстовых
правок даёт побайтно исходный broker. Common/Chain/serialization не правятся.
Никакой Perl или foreign module не импортирован, AST broker разобран как текст.
Python smoke совпадает по SHA с исходным pinned runtime из старого FREEZE.

Путь записи: конечный write-all, проверка integer return в1..remaining,
accounting только принятых bytes, flush; rotation закрывает старый writer,
fsync, сравнивает fstat/size, затем читает закрытый pathname O_NOFOLLOW,
проверяет dev/ino/size/mtime/hash и отсутствие лишнего byte. Closed receipt
также write-all/flush/fsync/close/readback. Новый shard открывается только
после успешного возврата всех этих действий. Ошибка делает writer poisoned;
cleanup не выдаёт его за successful close, исключение выходит в STOP broker.
Final closed-response отправляется только после успешного close/readback.
Обычные responses не обещают закрытия ещё текущего неполного shard.

У writer один active file; verifier fd закрывается finally; receipt fd — with.
В smoke используются только собственные injection wrappers; они не копируются
в production writer. На настоящих fd проверяется cleanup и все bytes.
Сторонние численные функции/алгоритм не тестируются и не меняются.

Новые риски: задержки fsync, дополнительное чтение и metadata, новые fail-closed
отказы storage/identity; они расходуют прежний deadline и audit cap, а не новый
бюджет. Нет cgroup/realtime/crash-durability guarantee. Readback сейчас не
предотвращает позднюю порчу, поэтому старый end-to-end verifier не исключается.
Проверка не устанавливает, чем вызвана историческая потеря35 кадров.

Smoke criteria и15 fixtures уже находятся в закреплённых PROTOCOL_RU.md,
smoke.py и SMOKE_FREEZE.json. После исхода они не меняются. Этот пакет не имеет
launcher нового пилота и не разрешает запуск broker или remaining controls.
