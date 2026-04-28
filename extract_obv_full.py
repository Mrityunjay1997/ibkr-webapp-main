with open('templates/morfeo.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the complete OBV row
print("=" * 140)
print("COMPLETE OBV INDICATOR ROW")
print("=" * 140)
print()

# Look for the tr that contains OBV
for i in range(430, 465):
    if i < len(lines):
        line = lines[i].rstrip()
        print(f"Line {i+1:4d}: {line}")
