# Минимальная граница интеграции — пока не исполнялась

Основание: pinned original2c7ad49cd4f4fa852168a8ce295bf739bf076adc, ReadLM.pm20–55; JMSmoothing.pm6–64; MCTS87–99,266–310; beam87–99,200–205; FreqAnalysis.pm. В загруженные LM пишет только ReadLM. В runtime все обращения к LM — индексированные чтения JMSmoothing; итерации keys/each/values по LM, удаления и пользовательские STORE отсутствуют. Иные hash solver — отдельные структуры, их порядок нельзя менять.

| Семантика оригинала | Обязательство нового слоя |
|---|---|
| chomp одного LF; split по серии TAB; assign1/2/3 ключей и значения | Полный census удостоверяет узкий домен точного количества полей. Никаких strip/Unicode/casefold/числовой нормализации |
| Повторный tuple key перезаписывает значение | Сохранить все строки; при доказанной сортировке upper_bound−1 возвращает последнюю равную строку |
| Значение хранится как Perl PV, числом становится у потребителя | Передать точные ASCII bytes/hex, восстановить Perl string; никогда JSON number/Python float |
| Missing leaf→undef; false value→0 в24–26; false unigram→`<u>` в42–43 | Не смешивать found/undefined/empty/`0`/`0.0`; не заменять truth-test на exists/defined или на probability>0. Пустые/undef значения отсутствуют только если это подтвердит census; общий permissive loader не обещается |
| Отсутствующий промежуточный hash может autovivify | На каждый score создавать обычные малые hash, позволить оригиналу autovivification; затем освободить. Не хранить фиктивные prefixes в дисковом источнике |
| Каждый log/sum идёт слева направо по токенам; char затем word; исходные lambdas/x | JMSmoothing.pm остаётся byte-identical, включая порядок операций, проверки и начало/конец. Не вводить нового backoff: отсутствующие higher orders дают0, а не рекурсивный backoff |
| Char whitespace→underscore; unknown replacement отдельно в char/word | Prefetch повторяет только формирование ключей; окончательный arithmetic path остаётся оригинальным. Не добавлять sentence markers/нормализацию |
| ties: строгий>, stable sort где задан; часть обходов hash | Сохранить solver lines, hash seed/perturb/env/порядок вставок и кандидатов. Изменённые allocation/timing требуют trajectory differential; равенство всей траектории пока не установлено |

Минимальное изменение будущего MCTS: вместо шести полных ReadLM loads открыть проверенные disk manifests; заменить только вызов ProbCharWord на thin prefetch-wrapper. Wrapper собирает нужные строки, вызывает **неизменённую** JMSmoothing::ProbCharWord с шестью локальными обычными hash. NoSpace, patlst adapter, word membership/maxlen, scorer, candidate selection, iteration count и search state не меняются. Не использовать tied nested hash: он потребует много FETCH, сложного STORE при autovivification и может размножать RPC.

Две стадии на score: U запрашивает unigrams исходных char/word токенов плюс`<u>`; N после штатного Perl unknown replacement запрашивает только используемые bi/trigrams. Для87 букв и штатной одно-пробельной сегментации N_char≤173,N_word≤87. Без экономии на одинаковых ключах U≤262записи, N≤514записей; всего≤776, плюс≤6 token-level hash roots. U содержит≤266 исходных байтов токенов. После unknown replacement длина каждого заменённого токена может вырасти до3: поэтому сумма длин char/word токенов≤3×(173+87)=780, а суммарная длина токенов в bi/trigram запросах N≤5×780=3900; hex удваивает. Для представления запроса `[table,[hex1,...]]` overhead≤24B/запись плюс128B/header: U<7KiB,N≤20264B<21KiB. Один request каждой стадии отправляется целиком, затем читаются все responses; встречных очередей запросов нет. Responses128записей/кадр, source probability≤96B; общий cap65536, проектный response chunk<32768. Две зависимые request/response фазы, а не сотни отдельных round trips. Эта консервативная граница учитывает расширение unknown и исправлена при статическом review до единственной попытки. Фактический wire-code ещё не написан/не исполнялся; эту конструкцию надо проверить отдельным transport regression.

При превышении87-letter/segmentation/token/frame domain — явный STOP, не truncation или fallback. Пустые ключи начала цикла не требуют fake LM rows: original i>=1/i>=2 guards уже пропускают такие обращения. Специальный`<u>` должен быть включён в U даже если не встретился буквально; missing `<u>` сохраняет исходную ошибку/log-domain, не заменяется новой вероятностью.

Cache: readonly exact key=(table,tuple), положительные и отрицательные ответы; LRU≤4096 entries, payload≤4096×(384+96)=1966080B. Промах не становится permanent absence при другом table ID. Eviction/caller mutation не меняют lookup. Count/payload bounds не равны полному RSS: object overhead, allocator, pagecache и Perl hash overhead отдельно; будущий broker AS-cap обязателен. Тест используетcapacity3, чтобы действительно пройти eviction.

Индекс на диске даёт≤ceil(log2(N+1))+1 record reads/промах; каждый pread≤512B+16B offsets, O(1) workspace. Лимиты файлов/запросов конечны. Но776 miss×около24 сравнений на каждый score могут оказаться медленными; cache может помочь, измеренная end-to-end производительность пока неизвестна. Это не обещание «дешёвого IPC» или гарантии завершения поиска в прежние сроки. Ограниченный benchmark ниже — только lookup на36 фиксированных намерениях, не имитация MCTS.

Главное реальное снятие памяти: не создавать около1,9GiB исходных шести Perl LM hash. Полный search peak остаётся неизвестен: candidate arrays/sort, `%newkeyhash`, tree/seen/score maps, segmentation и IPC copies остаются. Новый disk backend не разрешает автоматически full87/target и не меняет прежний P SKIP.

Первичные справочники (прочитаны, без Perl execution):
- https://perldoc.perl.org/5.38.2/functions/split — TAB+, trailing fields и list-assignment пределы; некорректные/лишние поля не нормализуем молча.
- https://perldoc.perl.org/5.38.2/functions/chomp — LF/record separator.
- https://perldoc.perl.org/5.38.2/functions/exists — exists/defined/truth различны; промежуточная autovivification.
- https://perldoc.perl.org/5.38.2/perldata — scalar string/numeric и Boolean semantics.
- https://perldoc.perl.org/5.38.2/perlrun#PERL_PERTURB_KEYS — hash traversal controls;0 не обещает переносимость между окружениями.

Непроверенное после успешного storage test: реальный Perl string→NV conversion/history, побитовые scores, unknown/пограничные случаи через новый prefetch, ordered candidates/ties/keys, IPC latency, память/скорость полного search. Для этого нужен отдельный замороженный ограниченный differential нового glue с неизменённым JMSmoothing; в данном scope он не запускается. P01 повторно не используется как калибровка.
