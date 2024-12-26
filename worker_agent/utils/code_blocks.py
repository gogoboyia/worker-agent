import re


def extract_code(text):
    result = []
    code_block_started = False
    code = ''
    lang = ''
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if not code_block_started:
            if line.startswith('```'):
                code_block_started = True
                lang = line[3:].strip()
                if not lang:
                    lang = None
                i += 1
                continue
        else:
            if line.startswith('```'):
                code_block_started = False
                result.append({
                    'content': code.rstrip('\n'),
                    'type': lang,
                    'path': extract_path(code)
                })
                code = ''
                lang = ''
                i += 1
                continue
            else:
                code += line + '\n'
        i += 1

    return result

def extract_path(file_content):
    first_line = file_content.split("\n")[0].strip()
    if first_line.startswith("#"):
        path_info = re.sub(r"^#\s*\.?\/?", "", first_line).strip()
        return path_info
    else:
        return None