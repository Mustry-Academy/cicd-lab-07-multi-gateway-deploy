# jar-files/jar/

Library JARs the deploy copies into the gateway's `lib/core/gateway/` (loaded
at boot — the deploy restarts the gateway when one changes). Pin exact
versions and record where every JAR came from:

| JAR | Source | Checksum (sha256) |
|---|---|---|
| `commons-csv-1.14.1.jar` | [Maven Central](https://repo1.maven.org/maven2/org/apache/commons/commons-csv/1.14.1/commons-csv-1.14.1.jar) | `32be0e1e76673092f5d12cb790bd2acb6c2ab04c4ea6efc69ea5ee17911c24fe` |

commons-csv on purpose: the Ignition image already bundles commons-lang3,
commons-text, guava and friends under `lib/core/common/`, so importing those
would succeed without the pipeline shipping anything. commons-csv is NOT
bundled — if the import works, the deploy really did put the JAR there.

Use it from any project script:

```python
from org.apache.commons.csv import CSVFormat
from java.io import StringReader
records = CSVFormat.DEFAULT.parse(StringReader("oats,water,salt")).getRecords()
fields = list(records[0])   # ['oats', 'water', 'salt'] — Stephan's Part 2 challenge
```
