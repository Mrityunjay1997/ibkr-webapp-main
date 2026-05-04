# Exclude Stocks from Scans - User Guide

## Overview

The **Exclude Stocks from Scans** feature allows you to manage a list of stocks that will be excluded from your scanner and analysis. You can:

- Add/remove individual stocks to exclude
- Save multiple named exclusion lists for different strategies
- Load and apply saved exclusion lists
- Import exclusion lists from CSV files
- Export your current exclusion list to CSV

## Accessing the Feature

Navigate to: `http://your-app:port/exclude-stocks`

## Features

### 1. Current Exclusion List

**Add Stocks**
- Enter one or more stock symbols separated by commas (e.g., `AAPL, MSFT, GOOGL`)
- Click "Add Stocks" to add them to the current exclusion list
- The list updates in real-time

**Remove Individual Stocks**
- Click the "Remove" button next to any stock in the list
- The stock is immediately removed from the exclusion list

**View Stock Count**
- The number of currently excluded stocks is displayed at the top of the list

### 2. Save & Load Exclusion Lists

**Save Current List**
- Enter a name for your exclusion list (e.g., "Penny Stocks", "My Blacklist")
- Click "Save List" to save or update an existing list with the same name
- Click "Save As New" to create a new list (will error if name already exists)

**Saved Lists Display**
- All saved lists are shown as cards displaying:
  - List name
  - Number of stocks in the list
  - Creation date

**Load a Saved List**
- Click "View" on any saved list card to see its details
- Click "Apply" to load the list and make it your current exclusion list
- Click "Delete" to permanently remove a saved list

### 3. Import/Export

**Export to CSV**
- Click "Export to CSV" to download your current exclusion list as a CSV file
- Format: One ticker symbol per line with a header row
- Useful for backup or sharing exclusion lists

**Import from CSV**
- Select a CSV file from your computer
- Click "Import CSV" to add all stocks from the file
- CSV format: One ticker per line, or a "Symbol" column header
- Stocks are added to your current exclusion list (not replacing)

### 4. Manage Exclusions

**Clear All**
- Click "Clear All" to remove all stocks from the current exclusion list
- Confirmation dialog will appear before clearing

## API Endpoints (for Advanced Users)

All operations are backed by REST APIs:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/exclude/list` | GET | Get current exclusion list |
| `/exclude/add` | POST | Add stocks to current list |
| `/exclude/remove` | POST | Remove stock from current list |
| `/exclude/clear` | POST | Clear entire exclusion list |
| `/exclude/save` | POST | Save current list with a name |
| `/exclude/load/<name>` | GET | Load a saved exclusion list |
| `/exclude/apply/<name>` | POST | Apply (load and set current) a saved list |
| `/exclude/delete/<name>` | DELETE | Delete a saved exclusion list |
| `/exclude/lists` | GET | List all saved exclusion lists |
| `/exclude/import-csv` | POST | Import from CSV file |
| `/exclude/export-csv` | GET | Export current list as CSV |

## Storage

- **Current Exclusion List**: Stored in `watchlists/excluded_stocks.json`
- **Saved Lists**: Stored as `watchlists/exclude_<name>.json` files

## Example Workflows

### Workflow 1: Create and Use Multiple Exclusion Lists

1. Start with an empty exclusion list
2. Add stocks: "PENNY1, PENNY2, PENNY3"
3. Save as "Penny Stocks" using "Save As New"
4. Clear and add different stocks: "BLUE1, BLUE2, BLUE3"
5. Save as "Blue Chip Exclusions" using "Save As New"
6. Switch between them by clicking "Apply" on each saved list

### Workflow 2: Import Exclusions from File

1. Prepare a CSV file with ticker symbols
2. Navigate to "Import/Export" section
3. Select your CSV file
4. Click "Import CSV"
5. Stocks are added to current exclusion list

### Workflow 3: Backup and Share

1. Click "Export to CSV" to backup your current exclusion list
2. Share the CSV file with colleagues
3. They can import it using the "Import from CSV" feature

## Tips

- Use descriptive names for your saved lists (e.g., "High Volatility Stocks", "Company Blacklist")
- Export your important exclusion lists regularly as backups
- Delete unused exclusion lists to keep your list organized
- Import exclusion lists from colleagues by having them export to CSV
- The exclusion list is case-insensitive (AAPL and aapl are the same)

## Troubleshooting

**"List already exists" error when saving**
- Use "Save List" to overwrite an existing list
- Or use "Save As New" with a different name

**Stocks not appearing after adding**
- Check for proper comma separation or spaces
- Ensure stock symbols are valid (e.g., AAPL, not "Apple")

**Import CSV not working**
- Verify CSV format: one ticker per line or with a "Symbol" column header
- Check for hidden characters or encoding issues

## Integration with Scanner

Once you have stocks in your exclusion list, the scanner will automatically skip any of these stocks when performing scans. This helps you focus on stocks you're interested in and avoid repeated analysis of stocks you've already decided to exclude.
