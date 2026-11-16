import re
from dataclasses import dataclass

CHUNK_CHARS = 4000
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
MATH = re.compile(r"^ {0,3}(\$\$|\\\[)")
TABLE_SEPARATOR = re.compile(r"[|: -]+")
# Character.isWhitespace excludes nonbreaking spaces and includes ASCII separators.
JAVA_WHITESPACE = "\t\n\v\f\r\x1c\x1d\x1e\x1f \u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2008\u2009\u200a\u2028\u2029\u205f\u3000"
JAVA_TRIM = "".join(map(chr, range(33)))


def char_count(text: str) -> int:
    return len(text.encode("utf-16-le", errors="surrogatepass")) // 2


def has_delimiter(line: str, delimiter: str, start: int) -> bool:
    for match in re.finditer(re.escape(delimiter), line[start:]):
        index = start + match.start()
        prefix = line[:index]
        if (len(prefix) - len(prefix.rstrip("\\"))) % 2 == 0:
            return True
    return False


@dataclass
class MarkdownState:
    fence: str = ""
    math: str = ""

    @property
    def closed(self) -> bool:
        return not (self.fence or self.math)

    def advance(self, line: str) -> None:
        if self.math:
            if has_delimiter(line, self.math, 0):
                self.math = ""
            return

        if marker := FENCE.match(line):
            mark = marker[1]
            if not self.fence:
                self.fence = mark
            elif mark.startswith(self.fence):
                self.fence = ""
            return

        if not self.fence and (opening := MATH.match(line)):
            close = "$$" if opening[1] == "$$" else r"\]"
            if not has_delimiter(line, close, opening.end()):
                self.math = close


def complete_fragment(text: str) -> bool:
    state = MarkdownState()
    for line in text.split("\n"):
        state.advance(line)
    return state.closed


def markdown_blocks(text: str):
    state = MarkdownState()
    lines = []
    for line in text.split("\n"):
        state.advance(line)
        if state.closed and not line.strip(JAVA_WHITESPACE):
            if lines:
                yield "\n".join(lines)
                lines = []
        else:
            lines.append(line)
    if lines:
        yield "\n".join(lines)


def is_table_separator(line: str) -> bool:
    return "---" in line and TABLE_SEPARATOR.fullmatch(line.strip(JAVA_WHITESPACE)) is not None


def split_large_block(block: str):
    """Break at lines, carrying fence or table context into the next fragment."""
    state = MarkdownState()
    lines = block.split("\n")
    fragment = []
    size = prefix_size = 0
    fence_open = ""
    table_header = []
    previous_table_row = False

    index = 0
    while index < len(lines):
        line = lines[index]
        fence = state.fence
        state.advance(line)
        end = index + 1
        # Move the entire display formula across a boundary, even when it exceeds the limit.
        while state.math and end < len(lines):
            state.advance(lines[end])
            end += 1
        formula = not fence and MATH.match(line) is not None
        table_row = not formula and line.lstrip(JAVA_WHITESPACE).startswith("|")
        unit = lines[index:end]
        unit_size = sum(char_count(item) + 1 for item in unit)

        if size > prefix_size and size + unit_size > CHUNK_CHARS:
            if fence:
                fragment.append(fence)
            yield "\n".join(fragment)
            fragment = [fence_open] if fence else (table_header.copy() if table_row else [])
            size = prefix_size = sum(char_count(item) + 1 for item in fragment)

        fragment.extend(unit)
        size += unit_size
        if state.fence and not fence:
            fence_open = line
        if formula:
            table_header = []
        elif (
            table_row
            and not previous_table_row
            and end < len(lines)
            and not is_table_separator(line)
            and is_table_separator(lines[end])
        ):
            table_header = [line, lines[end]]
        previous_table_row = table_row
        index = end

    if fragment:
        yield "\n".join(fragment)


def split_for_polish(text: str) -> list[str]:
    if char_count(text) <= CHUNK_CHARS:
        return [text]
    chunks = []
    current = ""
    current_size = 0
    for block in markdown_blocks(text):
        block_size = char_count(block)
        if current and current_size + block_size + 2 > CHUNK_CHARS:
            chunks.append(current)
            current = ""
            current_size = 0
        if block_size > CHUNK_CHARS:
            chunks.extend(split_large_block(block))
        elif current:
            current += "\n\n" + block
            current_size += block_size + 2
        else:
            current, current_size = block, block_size
    if current:
        chunks.append(current)
    return chunks or [text]
