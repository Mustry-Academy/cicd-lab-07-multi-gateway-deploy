"""plant.strings -- string helpers backed by the commons-lang3 library JAR."""


def flip(text):
    """Reverse a string with org.apache.commons.lang3 (Part 2, JAR challenge)."""
    from org.apache.commons.lang3 import StringUtils
    return StringUtils.reverse(text)
