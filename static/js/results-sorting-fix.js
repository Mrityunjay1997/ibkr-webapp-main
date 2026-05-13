/**
 * Results Sorting and Display Fix
 * Addresses three main issues:
 * 1. Headers disappearing when sorting by indicator
 * 2. Low-to-high sorting layout issues with prices spread out
 * 3. News headlines need stock symbol for clarity
 */

// ============================================================
// CONFIGURATION
// ============================================================
const RESULTS_CONFIG = {
    stickyHeaderZIndex: 1000,
    tableClass: 'results-table',
    headerRowClass: 'results-header-row',
    sectionHeaderClass: 'section-indicator-header',
    newsItemClass: 'news-item-with-symbol'
};

// ============================================================
// 1. MAKE TABLE HEADERS STICKY (Fix disappearing headers)
// ============================================================
function makeHeadersSticky() {
    const style = document.createElement('style');
    style.textContent = `
        /* Results table with sticky headers */
        .${RESULTS_CONFIG.tableClass} {
            width: 100%;
            border-collapse: collapse;
            table-layout: auto;
        }
        
        /* Sticky header rows - stay in place when scrolling */
        .${RESULTS_CONFIG.tableClass} thead {
            position: sticky;
            top: 0;
            z-index: ${RESULTS_CONFIG.stickyHeaderZIndex};
            background: #f5f5f5;
            border-bottom: 2px solid #333;
        }
        
        .${RESULTS_CONFIG.headerRowClass} {
            position: sticky;
            top: 0;
            z-index: ${RESULTS_CONFIG.stickyHeaderZIndex};
            background: #e8e8e8;
            border-bottom: 1px solid #999;
            font-weight: bold;
            padding: 10px 8px;
            text-align: left;
        }
        
        /* Indicator section headers (e.g., "FastSMA Results") */
        .${RESULTS_CONFIG.sectionHeaderClass} {
            position: sticky;
            top: 50px;
            z-index: ${RESULTS_CONFIG.stickyHeaderZIndex - 1};
            background: #d0d0d0;
            border-bottom: 2px solid #666;
            font-weight: 600;
            padding: 12px 8px;
            margin-top: 15px;
        }
        
        /* Prevent header overlap with content */
        .${RESULTS_CONFIG.tableClass} tbody tr {
            border-bottom: 1px solid #ddd;
        }
        
        /* News items with stock symbol */
        .${RESULTS_CONFIG.newsItemClass} {
            padding: 10px 8px;
            margin: 8px 0;
            border-left: 4px solid #0073aa;
            background: #f0f8ff;
            border-radius: 3px;
        }
        
        .${RESULTS_CONFIG.newsItemClass} .news-symbol {
            font-weight: 700;
            color: #0073aa;
            margin-right: 8px;
            display: inline-block;
            min-width: 50px;
        }
        
        .${RESULTS_CONFIG.newsItemClass} .news-headline {
            display: inline;
            color: #333;
        }
    `;
    document.head.appendChild(style);
}

// ============================================================
// 2. IMPROVE SORTING LAYOUT (Fix low-to-high spacing)
// ============================================================

/**
 * Render results with proper table formatting and sorting capability
 * Fixes the issue where low-to-high sorting spreads content unnecessarily
 */
function renderResultsTable(data, sortBy = 'symbol', sortDir = 'asc') {
    const container = document.getElementById('add1');
    if (!container) return;
    
    let html = '';
    
    // Group results by indicator/category
    for (const [groupName, stocks] of Object.entries(data)) {
        if (!stocks || stocks.length === 0) continue;
        
        // Sort the stocks
        let sortedStocks = [...stocks];
        sortedStocks = sortStocks(sortedStocks, sortBy, sortDir);
        
        // Add group header
        html += `<div class="${RESULTS_CONFIG.sectionHeaderClass}">
                    ${groupName} (${sortedStocks.length} results)
                    <span style="float: right; font-size: 12px; color: #666;">
                        Sort: 
                        <select onchange="changeSortOrder(this.value, '${groupName}')">
                            <option value="symbol_asc" ${sortBy === 'symbol' && sortDir === 'asc' ? 'selected' : ''}>Symbol A-Z</option>
                            <option value="symbol_desc" ${sortBy === 'symbol' && sortDir === 'desc' ? 'selected' : ''}>Symbol Z-A</option>
                            <option value="price_asc" ${sortBy === 'price' && sortDir === 'asc' ? 'selected' : ''}>Price Low to High</option>
                            <option value="price_desc" ${sortBy === 'price' && sortDir === 'desc' ? 'selected' : ''}>Price High to Low</option>
                            <option value="change_asc" ${sortBy === 'change' && sortDir === 'asc' ? 'selected' : ''}>Change Low to High</option>
                            <option value="change_desc" ${sortBy === 'change' && sortDir === 'desc' ? 'selected' : ''}>Change High to Low</option>
                        </select>
                    </span>
                 </div>`;
        
        // Add table
        html += `<table class="${RESULTS_CONFIG.tableClass}">
                    <thead>
                        <tr>
                            <th onclick="sortResultsBy('symbol', this)" class="sortable-header">Symbol</th>
                            <th onclick="sortResultsBy('price', this)" class="sortable-header">Price</th>
                            <th onclick="sortResultsBy('change', this)" class="sortable-header">% Change</th>
                            <th>Indicators Match</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>`;
        
        // Add stock rows
        for (const stock of sortedStocks) {
            const symbol = stock.ticker || stock.symbol || 'N/A';
            const price = parseFloat(stock.price || 0).toFixed(2);
            const change = parseFloat(stock.change || 0).toFixed(2);
            const changeColor = change >= 0 ? '#00aa00' : '#cc0000';
            
            html += `<tr data-symbol="${symbol}">
                        <td><strong>${symbol}</strong></td>
                        <td>$${price}</td>
                        <td style="color: ${changeColor}; font-weight: bold;">${change}%</td>
                        <td>${getIndicatorsSummary(stock)}</td>
                        <td>
                            <button class="btn btn-xs btn-info" onclick="viewStockDetails('${symbol}')">View</button>
                            <button class="btn btn-xs btn-success" onclick="buyStock('${symbol}')">Buy</button>
                        </td>
                    </tr>`;
        }
        
        html += `    </tbody>
                 </table>`;
        
        // Add news section if available
        const newsData = extractNewsForGroup(stocks, groupName);
        if (newsData && newsData.length > 0) {
            html += renderNewsSection(newsData);
        }
        
        html += '<br><br>';
    }
    
    container.innerHTML = html;
    makeHeadersSticky();
}

/**
 * Sort stocks array by specified field
 */
function sortStocks(stocks, sortBy = 'symbol', direction = 'asc') {
    const sorted = [...stocks];
    
    sorted.sort((a, b) => {
        let aVal = a[sortBy] || '';
        let bVal = b[sortBy] || '';
        
        // Convert to numbers for numeric fields
        if (sortBy === 'price' || sortBy === 'change' || sortBy === 'volume') {
            aVal = parseFloat(aVal) || 0;
            bVal = parseFloat(bVal) || 0;
        } else if (sortBy === 'symbol' || sortBy === 'ticker') {
            aVal = String(aVal).toUpperCase();
            bVal = String(bVal).toUpperCase();
        }
        
        let comparison = 0;
        if (aVal < bVal) comparison = -1;
        if (aVal > bVal) comparison = 1;
        
        return direction === 'asc' ? comparison : -comparison;
    });
    
    return sorted;
}

/**
 * Get summary of indicators matched for a stock
 */
function getIndicatorsSummary(stock) {
    const indicators = [];
    
    // Check various indicator fields
    const indicatorFields = [
        'FastSMA', 'MediumSMA', 'SlowSMA', 'RSI', 'VWAP', 'OBV',
        'FastEMA', 'SlowEMA', 'ATR', 'PrevClose', 'LowOfDay', 'HighOfDay'
    ];
    
    for (const field of indicatorFields) {
        if (stock[field]) {
            indicators.push(field);
        }
    }
    
    return indicators.length > 0 ? indicators.join(', ') : 'None';
}

/**
 * Extract news articles for a group and include stock symbols
 */
function extractNewsForGroup(stocks, groupName) {
    const newsItems = [];
    
    for (const stock of stocks) {
        if (stock.news && Array.isArray(stock.news)) {
            for (const article of stock.news) {
                newsItems.push({
                    symbol: stock.ticker || stock.symbol || 'UNKNOWN',
                    headline: article.headline || article.title || '',
                    source: article.source || article.provider || 'Unknown',
                    date: article.date || article.datetime || '',
                    articleId: article.articleId || '',
                    provider: article.provider || ''
                });
            }
        }
    }
    
    return newsItems;
}

/**
 * Render news section with stock symbols
 * This fixes the issue where news headlines didn't show which stock they belong to
 */
function renderNewsSection(newsItems) {
    if (!newsItems || newsItems.length === 0) return '';
    
    let html = '<div style="margin-top: 20px; padding: 15px; background: #fffaf0; border-left: 4px solid #ff8c00; border-radius: 4px;">';
    html += '<h4 style="margin-top: 0; color: #ff6600;">📰 Related News Headlines (' + newsItems.length + ')</h4>';
    
    for (const item of newsItems) {
        html += `<div class="${RESULTS_CONFIG.newsItemClass}">
                    <span class="news-symbol">[${item.symbol}]</span>
                    <span class="news-headline">${escapeHtml(item.headline)}</span>
                    <span style="color: #999; font-size: 11px; margin-left: 10px;">
                        ${item.source} • ${formatDate(item.date)}
                    </span>`;
        
        if (item.articleId && item.provider) {
            html += `<br><small><a href="#" onclick="openNewsArticleModal('${item.provider}', '${item.articleId}'); return false;" style="color: #0073aa; text-decoration: none;">Read full article →</a></small>`;
        }
        
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

/**
 * Helper: Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return 'Recently';
    try {
        const date = new Date(dateStr);
        const today = new Date();
        const diff = today - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);
        
        if (minutes < 60) return minutes + 'm ago';
        if (hours < 24) return hours + 'h ago';
        if (days < 7) return days + 'd ago';
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch (e) {
        return 'Recently';
    }
}

/**
 * Helper: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Sort results by a specific column
 */
function sortResultsBy(field, headerElement) {
    const currentSort = headerElement.getAttribute('data-sort-dir') || 'asc';
    const newSort = currentSort === 'asc' ? 'desc' : 'asc';
    
    headerElement.setAttribute('data-sort-dir', newSort);
    
    // Update all sortable headers
    document.querySelectorAll('.sortable-header').forEach(h => {
        if (h !== headerElement) {
            h.removeAttribute('data-sort-dir');
        }
    });
    
    // Re-render with new sort
    const container = document.getElementById('add1');
    if (container && container.resultsData) {
        renderResultsTable(container.resultsData, field, newSort);
    }
}

/**
 * Change sort order from dropdown
 */
function changeSortOrder(value, groupName) {
    const [sortBy, sortDir] = value.split('_');
    const container = document.getElementById('add1');
    if (container && container.resultsData) {
        renderResultsTable(container.resultsData, sortBy, sortDir);
    }
}

/**
 * Store results data for re-rendering
 */
function storeResultsData(data) {
    const container = document.getElementById('add1');
    if (container) {
        container.resultsData = data;
    }
}

// ============================================================
// 3. INTEGRATION WITH EXISTING RESULT DISPLAY
// ============================================================

/**
 * Wrapper for existing result rendering that enhances the display
 * Call this after your backend returns results
 */
function enhanceResultsDisplay(resultsData) {
    // Store data for sorting
    storeResultsData(resultsData);
    
    // Apply sticky headers CSS
    makeHeadersSticky();
    
    // Render with proper formatting
    renderResultsTable(resultsData, 'symbol', 'asc');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    makeHeadersSticky();
});

// Export functions for use in other scripts
window.enhanceResultsDisplay = enhanceResultsDisplay;
window.renderResultsTable = renderResultsTable;
window.sortStocks = sortStocks;
window.sortResultsBy = sortResultsBy;
window.changeSortOrder = changeSortOrder;
window.storeResultsData = storeResultsData;
