# BE-W16-WRITER-REPAIR-v1 — prospective writer repair и один собственный smoke

Старые BE-W16-v1 STOP, исходники, attempt, журналы и выведенный gap не изменяются.
Этот пакет не является новым freeze пилота и не разрешает поиск.

Изменяются только собственные файлы: добавляется runtime/verified_shards.py;
в копии runtime/broker.py подключается VerifiedShards с прежним tick,
добавляется final=False к send и close перед отправкой финального closed-ответа.
На обычном response завершены все закрытия, вызванные его записью/предшествующим
request; текущий неполный chunk не закрывается после каждого сообщения.
В финальном response журналируется прежний closed-пакет, затем последний chunk
flush→fsync→close→readback и закрытый receipt; только затем bytes идут в pipe.
При ошибке запись poisoned, response не отправляется, следующий chunk не открыт.

Формат >BI/JSON/LF, FRAME=65536, SHARD=8388608, seq/op/offset/values/done,
разбиение packet на блоки, порядок запросов и кандидатов, арифметика и ties
не меняются. common.py/Perl/scorer/search/входы/ключи/seed/gates не изменяются.
Влияние на wallclock есть: синхронизация и readback могут привести к прежнему
INCOMPLETE_BUDGET; время не добавляется. Прежние limits: 130 s work/180 s case,
1500 s pilot; broker 128 MiB AS, Perl 256 MiB, supervisor 128 MiB, максимум3.
8 MiB/file и96 MiB/case, входные memory gates и общий reserve прежние.
По пределу96 MiB raw journal и block≤65536 — не более13 chunks; каждый
closed receipt≤2048 B, все≤32768 B. Дополнительные receipts учитываются
в существующем общем evidence cap; это не добавленные32 KiB поверх cap.
Readback читает каждый chunk один раз блоками≤65536; хеши и metadata малы,
добавленный рабочий payload буфер≤128 KiB, отсутствует chunk-sized allocation.
Не более13 data fsync и13 receipt fsync; не более96 MiB дополнительного чтения
данных плюс32768 B receipts. Весь I/O учитывается внутри прежнего tick/deadline.
Fsync может блокироваться; cooperative tick не гарантирует realtime timeout.
Проверка подтверждает закрытые bytes на момент readback, не исключает позднюю
порчу, host crash/потерю directory entry или будущую внешнюю замену. Прежний
полный verifier и Library byte-readback остаются обязательными. Причину старой
потери эти меры не устанавливают.

## Frozen smoke (один запуск, без broker/Perl/моделей)

Только smoke.py + новый собственный verified_shards.py + Python stdlib.
Одна новая smoke_attempt, отказ при её существовании. Python3.12 -B -I -S.
AS64 MiB, CPU10 s, cooperative30 s, NOFILE64, FSIZE8 MiB, CORE0, процессов1;
никаких subprocess/thread/network. В stdout не более32768 B, файлов≤20 MiB
совокупно. Свежий gate: memory.max=8GiB, current<5468942336 B; disk free≥64MiB.
Системные fsync/read могут блокироваться; fixed loops ограничивают работу,
но30 s не объявляется hard-kill. При sessionID наблюдать тот же процесс.

Заранее фиксированы15 fixtures, без замены/добавления после результата:

1. POS_ROTATION: block=bytes(range(256))*256;127 полных blocks, block[:65535],
   b'Q',b'R',block. Рубежи8388607/8388608/8388609; chunks8388608 и65537 B.
   До открытия второго файла проверен closed receipt первого; последний
   фиктивный ACK допустим только после close/readback обоих. Независимый
   streaming comparator проверяет все bytes по указанной формуле.
2. POS_SHORT_RETURN: payload=b'0123456789abcdefghijklmnopqrstuv' (32 B),
   writer возвращает не более7 за write; полная запись и readback точны.
3–6. NEG_RETURN_NONE/ZERO/NEGATIVE/EXCESS: invalid write result отвергается.
7. NEG_FLUSH, 8. NEG_FSYNC, 9. NEG_CLOSE: injected OSError отвергается.
10. NEG_ROTATION_TRUNCATE:128 полных blocks (8 MiB); перед readback закрытого
    chunk отрезается ровно1 byte; следующая запись b'R' не открывает shard1,
    ACK не записан.
11. NEG_HASH:32 B, после close инвертируется первый byte; original mtime
    восстанавливается, чтобы проверка обязана была проверить hash.
12. NEG_REPLACE:32 B, pathname заменяется другим inode с теми же bytes.
13. NEG_APPEND:32 B, после close дописывается b'!'.
14. NEG_RECEIPT: ошибка создания closed receipt; completion ACK запрещён.
15. NEG_DEADLINE: tick выбрасывает deadline до первой записи.

PASS_SMOKE_ONLY требует обе позитивные точные сверки, ожидаемый отказ всех13
негативов, отсутствие ACK при отказе, следующий shard отсутствует после ошибки
ротации, poisoned writer не принимает продолжение, все собственные fd закрыты,
результат/файлы закрыты, exit0 и elapsed<30 s. Неожиданность=STOP, без повторов.
Код/критерии/исходные hashes закрепляются до запуска. Сохранить actual raw tool
stdout/exit, hashes закрытых результатов и точный Library ZIP readback.
PASS означает только этот writer-контракт на фиктивных bytes; не исправленный
pilot, не numerical equivalence и не объяснение старого STOP.
