with open('templates/morfeo.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Create a summary document
output = []
output.append("=" * 140)
output.append("OBV INDICATOR FORM ROWS - HTML STRUCTURE")
output.append("=" * 140)
output.append("")
output.append("LOCATION: Lines 438-459 (main OBV indicator form row)")
output.append("")
output.append("STRUCTURE BREAKDOWN:")
output.append("- Line 438: Opening <tr> tag for OBV row")
output.append("- Line 439: OBV label header cell")
output.append("- Line 440-443: Time Frame column (tf_obv)")
output.append("  * Line 442: <div id='tf_obv'> with OBV_tf parameter (OBV time frame selector)")
output.append("- Line 444-446: Period input column")
output.append("  * Line 445: <div id='nchangeinput8'> with OBV parameter (period value=5)")
output.append("- Line 447: Comparison operator column header (ComparisonOBV)")
output.append("- Line 448-450: Percentage column")
output.append("  * Line 449: <div id='changeinput8'> with PercentageOBV parameter (value='0')")
output.append("- Line 451-457: Enable/Checkbox columns")
output.append("  * Line 452-456: For loop iterating OBVBool (checkbox fields with yes/no formatting)")
output.append("- Line 458: Filter checkbox column")
output.append("  * Line 458: filterOBV parameter with cursor:pointer style")
output.append("- Line 459: Closing </tr> tag")
output.append("")
output.append("=" * 140)
output.append("FULL HTML CODE:")
output.append("=" * 140)
output.append("")

for i in range(438, 459):
    if i < len(lines):
        line = lines[i].rstrip()
        output.append(f"Line {i+1:4d}: {line}")

# Write to file
with open('obv_structure_summary.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print('\n'.join(output))
