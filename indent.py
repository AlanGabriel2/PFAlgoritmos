lines = open('main.py', 'r', encoding='utf-8').readlines()
start = -1
end = -1
for i, line in enumerate(lines):
    if '# Disparar con flechas' in line and 'dx, dy = 0, 0' in lines[i+1]:
        start = i
    if 'trigger_transition("MAP"' in line and 'else:' in lines[i-1]:
        end = i

if start != -1 and end != -1:
    new_lines = lines[:start]
    new_lines.append('            if not editor_mode:\n')
    for i in range(start, end+1):
        new_lines.append('    ' + lines[i])
    new_lines.extend(lines[end+1:])
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Success")
else:
    print(f"Failed. Start: {start}, End: {end}")
