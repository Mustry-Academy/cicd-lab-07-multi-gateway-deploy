# jar-files/jar/

Library JARs the deploy copies into the gateway's `lib/core/gateway/` (loaded
at boot — the deploy restarts the gateway when one changes). Pin exact
versions and record where every JAR came from:

| JAR | Source | Checksum (sha256) |
|---|---|---|
| `commons-lang3-3.19.0.jar` | [Maven Central](https://repo1.maven.org/maven2/org/apache/commons/commons-lang3/3.19.0/commons-lang3-3.19.0.jar) | `32733ab4bc90b45b63eb72677d886961003fd4ed113e07b1028f9877cb2ac735` |

Use it from any project script:

```python
from org.apache.commons.lang3 import StringUtils
flipped = StringUtils.reverse("Ignition")   # Stephan's Part 2 challenge
```
