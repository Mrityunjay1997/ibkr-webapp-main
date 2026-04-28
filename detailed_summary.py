with open('templates/morfeo.html', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Extract lines with OBV from 438 to 459
output = []
output.append("=" * 150)
output.append("OBV INDICATOR FORM ROWS - COMPLETE HTML STRUCTURE")
output.append("=" * 150)
output.append("")
output.append("FILE: templates/morfeo.html")
output.append("LINE RANGE: 438-459")
output.append("")
output.append("DESCRIPTION:")
output.append("This is the main OBV (On Balance Volume) indicator configuration row in the indicators table.")
output.append("It includes the following form controls:")
output.append("  1. OBV Label (Line 439)")
output.append("  2. OBV Time Frame selector (Line 442) - id='tf_obv'")
output.append("  3. OBV Period input (Line 445) - id='nchangeinput8', value=5")
output.append("  4. Comparison Operator selector (Line 447) - ComparisonOBV")
output.append("  5. Percentage input (Line 449) - id='changeinput8', value='0'")
output.append("  6. Enable/Checkbox fields (Lines 452-456) - OBVBool loop")
output.append("  7. Filter checkbox (Line 458) - filterOBV with cursor pointer style")
output.append("")
output.append("=" * 150)
output.append("DETAILED HTML STRUCTURE:")
output.append("=" * 150)
output.append("")

for i in range(438, 459):
    if i < len(lines):
        output.append(f"Line {i+1:4d}: {lines[i]}")

# Save to file
with open('obv_detailed_structure.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

# Print to console
print('\n'.join(output))
