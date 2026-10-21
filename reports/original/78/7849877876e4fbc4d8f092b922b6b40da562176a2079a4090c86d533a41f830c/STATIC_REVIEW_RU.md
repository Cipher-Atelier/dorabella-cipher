# Статический review; исполнения нет

59 проверок AST/data-only прошли (`STATIC_CHECKS.json`): Python syntax AST; 20 source/data файлов побайтово прежние; broker отличается только import/constructor; единственный вызов `pair('real')`; нет reference/adapted запусков; wiring observed verifier/binding/publication; в новых I/O-модулях нет spawn/network imports; прежние synthetic traces равны; JSON UTF-8 без BOM; attempt/T0 отсутствуют. Это не runtime test.

`broker.py.diff`, `run.py.diff`, `launch.py.diff` фиксируют все изменения к baseline. `readback.py` SHA остаётся `3c5e1917172c84ef61d56e947d6f283d3dde2096542703ab1ada563d1a722296`. Ни Perl, ни численная часть не менялись.

Ручная сверка: журнал пишет только broker; родитель сохраняет лишь отдельные stdout/stderr. Observer-файл readonly имеет независимый fd с той же dev/inode; pread не меняет offset writer. Progress audit unbuffered, проверяет short-write и cap. Ошибки не превращаются в completion; original broker exception/exit сохраняются. Закрытие всех observer handles предусмотрено и при исключении. Частично прочитанный verifier iterator имеет EOF=false; witness закрывает оставшиеся handles. Ни новые wrappers, ни old verifier сейчас не импортировались.

`verifier_binding.observed_real` фиксирует точный source SHA и код, созданный из этих source bytes. Это устраняет неоднозначность источника verifier для будущей попытки, но не доказывает, что такая неоднозначность вызвала старый сбой. Заменены только функции I/O; исходные real/ipc assertions исполнятся после отдельного согласия. При return фиксируется точное значение, при exception — repr и consumed reads; исходный result.json больше не единственный носитель утверждения о return.

Final binding сверяет writer intended/visible/closed hashes с consumed journal hash и final hash, dev/inode/size/stat, EOF/2244records, terminal waits, порядок timestamps. Источник критерия complete IPC по-прежнему исходный `readback.ipc`, включая count/close/word trace. Это дополнительные доказательства целостности, не изменение научного gate или численной терпимости.

Не проверено исполнением: фактический peak/overhead новых observer syscalls, завершение в старом deadline, runtime support нового кода, повторение старого сбоя. No-go при hash/runtime/resource/process несоответствии; никакого fallback. Новая попытка может завершиться STOP без научного отрицательного результата.

Старые result/archive/audit hashes проверяются при freeze; старые файлы не редактируются. Большие модели перечислены по исходным14 identities и будут заново проверены только перед разрешённым запуском.
