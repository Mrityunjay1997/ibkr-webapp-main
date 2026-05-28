/**
 * Dynamic Indicator Management System
 * Allows adding, removing, and configuring multiple indicators dynamically
 */

// Available indicator types and their properties
const INDICATOR_TYPES = {
    'FastSMA': { label: 'Fast SMA', defaultWindow: 5, hasTimeframe: true },
    'MediumSMA': { label: 'Medium SMA', defaultWindow: 10, hasTimeframe: true },
    'SlowSMA': { label: 'Slow SMA', defaultWindow: 20, hasTimeframe: true },
    'SMA1': { label: 'Additional SMA 1', defaultWindow: 30, hasTimeframe: true },
    'SMA2': { label: 'Additional SMA 2', defaultWindow: 50, hasTimeframe: true },
    'SMA3': { label: 'Additional SMA 3', defaultWindow: 200, hasTimeframe: true },
    'FastEMA': { label: 'Fast EMA', defaultWindow: 12, hasTimeframe: true },
    'SlowEMA': { label: 'Slow EMA', defaultWindow: 26, hasTimeframe: true },
    'EMA1': { label: 'Additional EMA 1', defaultWindow: 9, hasTimeframe: true },
    'EMA2': { label: 'Additional EMA 2', defaultWindow: 21, hasTimeframe: true },
    'RSI': { label: 'RSI', defaultWindow: 14, hasTimeframe: true },
    'VWAP': { label: 'VWAP', defaultWindow: 20, hasTimeframe: true },
    'OBV': { label: 'OBV', defaultWindow: 0, hasTimeframe: false },
    'FastOBV': { label: 'Fast OBV', defaultWindow: 5, hasTimeframe: false },
    'MediumOBV': { label: 'Medium OBV', defaultWindow: 10, hasTimeframe: false },
    'SlowOBV': { label: 'Slow OBV', defaultWindow: 20, hasTimeframe: false },
    'ATR': { label: 'ATR', defaultWindow: 14, hasTimeframe: true },
    'Candlestick1': { label: 'Candlestick 1', defaultWindow: 10, hasTimeframe: false },
    'Candlestick2': { label: 'Candlestick 2', defaultWindow: 10, hasTimeframe: false },
    'Candlestick3': { label: 'Candlestick 3', defaultWindow: 10, hasTimeframe: false },
    'Candlestick4': { label: 'Candlestick 4', defaultWindow: 10, hasTimeframe: false },
    'PrevClose': { label: 'Previous Close', defaultWindow: 0, hasTimeframe: false },
    'PctChange': { label: '% Change', defaultWindow: 0, hasTimeframe: false },
    'LowOfDay': { label: 'Low of Day', defaultWindow: 0, hasTimeframe: false },
    'HighOfDay': { label: 'High of Day', defaultWindow: 0, hasTimeframe: false },
};

const COMPARISON_OPERATORS = [
    { value: 'greater', label: '>' },
    { value: 'greaterEqual', label: '>=' },
    { value: 'lower', label: '<' },
    { value: 'lowerEqual', label: '<=' },
    { value: 'equal', label: '=' },
    { value: 'between', label: 'between' },
    { value: 'withinPercentAbove', label: 'Within % Above' },
    { value: 'withinPercentBelow', label: 'Within % Below' },
    { value: 'withinPercentEither', label: 'Within Either %' },
    { value: 'disabled', label: 'Not used' },
];

const TIMEFRAME_OPTIONS = [
    '1 min', '2 min', '5 min', '15 min', '1 hour', '1 day', '1 week', '1 month'
];

class IndicatorManager {
    constructor() {
        this.indicators = [];
        this.nextId = 0;
        this.loadFromForm();
    }

    /**
     * Load indicators from hidden form field or initialize empty
     */
    loadFromForm() {
        const field = document.getElementById('indicatorConfigField');
        if (field && field.value) {
            try {
                this.indicators = JSON.parse(field.value);
                this.nextId = Math.max(...this.indicators.map(i => i.id), -1) + 1;
            } catch (e) {
                console.error('Error loading indicators:', e);
                this.indicators = [];
                this.nextId = 0;
            }
        }
    }

    /**
     * Save indicators to hidden form field
     */
    saveToForm() {
        const field = document.getElementById('indicatorConfigField');
        if (field) {
            field.value = JSON.stringify(this.indicators);
        }
    }

    /**
     * Add a new indicator
     */
    addIndicator(type, window = null, comparison = 'disabled', percentage = 0, timeframe = '1 day', usePercentage = false) {
        const indicatorType = INDICATOR_TYPES[type];
        if (!indicatorType) {
            console.error('Unknown indicator type:', type);
            return null;
        }

        const indicator = {
            id: this.nextId++,
            type: type,
            window: window !== null ? window : indicatorType.defaultWindow,
            comparison: comparison,
            percentage: percentage,
            timeframe: timeframe,
            usePercentage: usePercentage,
            enabled: true
        };

        this.indicators.push(indicator);
        this.saveToForm();
        return indicator;
    }

    /**
     * Remove an indicator by ID
     */
    removeIndicator(id) {
        this.indicators = this.indicators.filter(i => i.id !== id);
        this.saveToForm();
    }

    /**
     * Update an indicator
     */
    updateIndicator(id, updates) {
        const indicator = this.indicators.find(i => i.id === id);
        if (indicator) {
            Object.assign(indicator, updates);
            this.saveToForm();
        }
    }

    /**
     * Get all enabled indicators
     */
    getEnabledIndicators() {
        return this.indicators.filter(i => i.enabled && i.comparison !== 'disabled');
    }

    /**
     * Render indicators table
     */
    renderIndicators(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (this.indicators.length === 0) {
            container.innerHTML = '<p class="text-muted">No indicators added. Click "Add Indicator" to get started.</p>';
            return;
        }

        let html = `
            <table class="table table-sm table-hover" style="font-size:0.9rem;">
                <thead>
                    <tr style="background-color:#f5f5f5;">
                        <th>Indicator</th>
                        <th>Timeframe</th>
                        <th>Number of Bars</th>
                        <th>Sign Indicator</th>
                        <th>Amount</th>
                        <th>Use %</th>
                        <th style="text-align:center; width:80px;">Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        this.indicators.forEach(indicator => {
            const indicatorType = INDICATOR_TYPES[indicator.type];
            const isDisabled = indicator.comparison === 'disabled';
            const rowClass = isDisabled ? 'text-muted' : '';

            html += `
                <tr class="${rowClass}" data-indicator-id="${indicator.id}">
                    <td><strong>${indicatorType.label}</strong></td>
                    <td>
                        ${indicatorType.hasTimeframe ? `
                            <select class="form-control form-control-sm timeframe-select" onchange="indicatorManager.updateIndicator(${indicator.id}, {timeframe: this.value}); indicatorManager.renderIndicators('indicatorsContainer');">
                                ${TIMEFRAME_OPTIONS.map(tf => `<option ${tf === indicator.timeframe ? 'selected' : ''}>${tf}</option>`).join('')}
                            </select>
                        ` : '—'}
                    </td>
                    <td>
                        <input type="number" class="form-control form-control-sm window-input" value="${indicator.window}" 
                            onchange="indicatorManager.updateIndicator(${indicator.id}, {window: parseInt(this.value) || 0}); indicatorManager.renderIndicators('indicatorsContainer');">
                    </td>
                    <td>
                        <select class="form-control form-control-sm comparison-select" onchange="indicatorManager.updateIndicator(${indicator.id}, {comparison: this.value}); indicatorManager.renderIndicators('indicatorsContainer');">
                            ${COMPARISON_OPERATORS.map(op => `<option value="${op.value}" ${op.value === indicator.comparison ? 'selected' : ''}>${op.label}</option>`).join('')}
                        </select>
                    </td>
                    <td>
                        <input type="number" step="0.01" class="form-control form-control-sm percentage-input" value="${indicator.percentage}" 
                            onchange="indicatorManager.updateIndicator(${indicator.id}, {percentage: parseFloat(this.value) || 0}); indicatorManager.renderIndicators('indicatorsContainer');">
                    </td>
                    <td style="text-align:center;" title="When checked, compare using a percentage threshold instead of an absolute value.">
                        <input type="checkbox" class="use-percentage-checkbox" ${indicator.usePercentage ? 'checked' : ''} 
                            onchange="indicatorManager.updateIndicator(${indicator.id}, {usePercentage: this.checked}); indicatorManager.renderIndicators('indicatorsContainer');">
                    </td>
                    <td style="text-align:center;">
                        <button class="btn btn-xs btn-danger" onclick="indicatorManager.removeIndicator(${indicator.id}); indicatorManager.renderIndicators('indicatorsContainer');" title="Remove">
                            <span class="glyphicon glyphicon-trash"></span>
                        </button>
                    </td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        container.innerHTML = html;
    }

    /**
     * Show add indicator modal/form
     */
    showAddIndicatorForm(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let html = `
            <div class="modal fade" id="addIndicatorModal" tabindex="-1" role="dialog">
                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Add Indicator</h5>
                            <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <form id="addIndicatorForm">
                                <div class="form-group">
                                    <label for="indicatorType">Indicator Type</label>
                                    <select id="indicatorType" class="form-control" required>
                                        <option value="">-- Select Indicator --</option>
                                        ${Object.entries(INDICATOR_TYPES).map(([key, type]) => 
                                            `<option value="${key}">${type.label}</option>`
                                        ).join('')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="indicatorComparison">Comparison Operator</label>
                                    <select id="indicatorComparison" class="form-control">
                                        ${COMPARISON_OPERATORS.map(op => 
                                            `<option value="${op.value}">${op.label}</option>`
                                        ).join('')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="indicatorPercentage">Threshold Value</label>
                                    <input type="number" id="indicatorPercentage" class="form-control" step="0.01" value="0">
                                </div>
                                <div class="form-check">
                                    <input type="checkbox" id="indicatorUsePercentage" class="form-check-input">
                                    <label class="form-check-label" for="indicatorUsePercentage">
                                        Use Percentage Value
                                    </label>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="indicatorManager.handleAddIndicatorSubmit();">Add Indicator</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
        $('#addIndicatorModal').modal('show');
    }

    /**
     * Handle adding indicator from form
     */
    handleAddIndicatorSubmit() {
        const type = document.getElementById('indicatorType').value;
        const comparison = document.getElementById('indicatorComparison').value;
        const percentage = parseFloat(document.getElementById('indicatorPercentage').value) || 0;
        const usePercentage = document.getElementById('indicatorUsePercentage').checked;

        if (!type) {
            alert('Please select an indicator type');
            return;
        }

        this.addIndicator(type, null, comparison, percentage, '1 day', usePercentage);
        this.renderIndicators('indicatorsContainer');
        $('#addIndicatorModal').modal('hide');
    }

    /**
     * Convert to form parameters for backend
     */
    toFormParameters() {
        const params = {};
        
        this.indicators.forEach((indicator, index) => {
            const prefix = indicator.type;
            const suffix = index > 0 ? index : '';
            
            params[prefix + suffix] = indicator.window;
            params['Comparison' + prefix + suffix] = indicator.comparison;
            params['Percentage' + prefix + suffix] = indicator.percentage;
            
            if (indicator.hasTimeframe) {
                params[prefix + '_tf' + suffix] = indicator.timeframe;
            }
        });

        return params;
    }
}

// Global instance
let indicatorManager = new IndicatorManager();

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we have the container
    if (document.getElementById('indicatorsContainer')) {
        indicatorManager.renderIndicators('indicatorsContainer');
    }
});
