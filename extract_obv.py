with open('templates/morfeo.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find OBV indicator form section (around line 439)
start_line = 438
end_line = 460

print("=" * 120)
print("OBV INDICATOR FORM STRUCTURE")
print("=" * 120)
print()

for i in range(start_line, end_line):
    if i < len(lines):
        print(f"Line {i+1:4d}: {lines[i]}", end='')
