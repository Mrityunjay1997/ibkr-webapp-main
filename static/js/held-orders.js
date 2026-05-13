/**
 * Held Orders Off-Market JavaScript
 * Handles UI for creating, managing, and monitoring held orders
 */

// Global state for held orders
let heldOrdersState = {
    enabled: false,
    activeOrders: [],
    refreshInterval: null
};

// ============================================================================
// UI Control Functions
// ============================================================================

function _hoOpenSettings() {
    alert("Held Orders Settings\n\nMonitoring interval: Every 1 second\nCheck conditions continuously while panel is visible");
}

function _hoTogglePanel() {
    const enabled = document.getElementById('ho_enabled').checked;
    heldOrdersState.enabled = enabled;
    
    const body = document.getElementById('ho_body');
    if (body) {
        body.style.display = enabled ? 'block' : 'none';
    }
    
    if (enabled) {
        _hoStartMonitoring();
    } else {
        _hoStopMonitoring();
    }
}

function _hoToggleOrderType() {
    const orderType = document.getElementById('ho_order_type').value;
    const limitPriceField = document.getElementById('ho_limit_price_field');
    
    if (orderType === 'market') {
        limitPriceField.style.display = 'none';
    } else {
        limitPriceField.style.display = 'block';
    }
}

function _hoToggleCandleEntry() {
    const use = document.getElementById('ho_use_candle_entry').checked;
    const config = document.getElementById('ho_candle_entry_config');
    if (config) {
        config.style.display = use ? 'block' : 'none';
    }
}

function _hoToggleMaEntry() {
    const use = document.getElementById('ho_use_ma_entry').checked;
    const config = document.getElementById('ho_ma_entry_config');
    if (config) {
        config.style.display = use ? 'block' : 'none';
    }
}

function _hoToggleCandleExit() {
    const use = document.getElementById('ho_use_candle_exit').checked;
    const config = document.getElementById('ho_candle_exit_config');
    if (config) {
        config.style.display = use ? 'block' : 'none';
    }
}

function _hoToggleMaExit() {
    const use = document.getElementById('ho_use_ma_exit').checked;
    const config = document.getElementById('ho_ma_exit_config');
    if (config) {
        config.style.display = use ? 'block' : 'none';
    }
}

// ============================================================================
// Create Held Order
// ============================================================================

async function _hoCreateOrder() {
    try {
        const symbol = document.getElementById('ho_symbol').value.toUpperCase().trim();
        const side = document.getElementById('ho_side').value;
        const quantity = parseInt(document.getElementById('ho_quantity').value);
        const orderType = document.getElementById('ho_order_type').value;
        const limitPrice = orderType === 'limit' 
            ? parseFloat(document.getElementById('ho_limit_price').value)
            : null;
        const tif = document.getElementById('ho_tif')?.value || 'DAY';
        const notes = document.getElementById('ho_notes')?.value || '';
        
        // Validate
        if (!symbol) {
            alert('Please enter a symbol');
            return;
        }
        if (isNaN(quantity) || quantity <= 0) {
            alert('Quantity must be > 0');
            return;
        }
        if (orderType === 'limit' && (!limitPrice || limitPrice <= 0)) {
            alert('Limit price must be > 0');
            return;
        }
        
        // Build entry conditions
        const entryConditions = [];
        
        // Candle breakout entry
        if (document.getElementById('ho_use_candle_entry').checked) {
            entryConditions.push({
                condition_type: 'candle_breakout',
                config: {
                    timeframe: document.getElementById('ho_candle_tf').value,
                    candles_to_check: parseInt(document.getElementById('ho_candle_lookback').value),
                    break_direction: document.getElementById('ho_candle_direction').value,
                    entry_offset_pct: parseFloat(document.getElementById('ho_candle_offset').value),
                    lookback_bars: parseInt(document.getElementById('ho_candle_lookback').value)
                }
            });
        }
        
        // MA crossover entry
        if (document.getElementById('ho_use_ma_entry').checked) {
            entryConditions.push({
                condition_type: 'ma_crossover',
                config: {
                    timeframe: document.getElementById('ho_ma_tf').value,
                    ma_type: document.getElementById('ho_ma_type').value,
                    ma_period: parseInt(document.getElementById('ho_ma_period').value),
                    cross_direction: document.getElementById('ho_ma_direction').value,
                    cross_offset_pct: parseFloat(document.getElementById('ho_ma_offset').value)
                }
            });
        }
        
        if (entryConditions.length === 0) {
            alert('Please select at least one entry condition');
            return;
        }
        
        // Build exit conditions
        const exitConditions = [];
        // (similar to entry conditions if needed)
        
        // Send to backend
        const response = await fetch('/held-orders/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: symbol,
                side: side,
                quantity: quantity,
                order_type: orderType,
                limit_price: limitPrice,
                tif: tif,
                entry_conditions: entryConditions,
                exit_conditions: exitConditions,
                notes: notes
            })
        });
        
        const result = await response.json();
        
        if (result.status === 'ok') {
            alert(`✓ Held order created!\nOrder ID: ${result.order_id}\n${symbol} ${side} ${quantity} shares`);
            _hoClearForm();
            _hoRefreshList();
        } else {
            alert(`✗ Error: ${result.message}`);
        }
    } catch (error) {
        console.error('Error creating held order:', error);
        alert(`Error: ${error.message}`);
    }
}

function _hoClearForm() {
    document.getElementById('ho_symbol').value = '';
    document.getElementById('ho_side').value = 'long';
    document.getElementById('ho_quantity').value = '100';
    document.getElementById('ho_order_type').value = 'limit';
    document.getElementById('ho_limit_price').value = '';
    document.getElementById('ho_use_candle_entry').checked = false;
    document.getElementById('ho_use_ma_entry').checked = false;
    document.getElementById('ho_candle_entry_config').style.display = 'none';
    document.getElementById('ho_ma_entry_config').style.display = 'none';
}

// ============================================================================
// Refresh & List Held Orders
// ============================================================================

async function _hoRefreshList() {
    try {
        const response = await fetch('/held-orders/list');
        const result = await response.json();
        
        if (result.status === 'ok') {
            heldOrdersState.activeOrders = result.orders;
            _hoDisplayOrdersList(result.orders);
        }
    } catch (error) {
        console.error('Error refreshing held orders:', error);
    }
}

function _hoDisplayOrdersList(orders) {
    const container = document.getElementById('ho_active_orders_list');
    if (!container) {
        console.log('No orders list container found');
        return;
    }
    
    if (orders.length === 0) {
        container.innerHTML = '<div style="padding: 10px; color: #999;">No active held orders</div>';
        return;
    }
    
    let html = '<div style="max-height: 400px; overflow-y: auto;">';
    
    for (const order of orders) {
        const conditionsText = order.entry_conditions
            .map(c => `${c.condition_type}`)
            .join(', ');
        
        const statusColor = order.status === 'triggered' ? '#ff9800' : 
                           order.status === 'executed' ? '#4caf50' : '#2196F3';
        
        html += `
        <div style="background: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; padding: 10px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="color: ${statusColor};">${order.symbol}</strong>
                    <span style="margin: 0 8px; color: #666;">|</span>
                    <strong>${order.side === 'long' ? 'BUY' : 'SELL'} ${order.quantity}</strong>
                    <span style="margin: 0 8px; color: #666;">@</span>
                    <span>${order.order_type === 'limit' ? order.limit_price : 'Market'}</span>
                </div>
                <button onclick="_hoCancelOrder('${order.order_id}')" style="padding: 4px 8px; background: #f44336; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">Cancel</button>
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: #666;">
                <div>Condition: ${conditionsText}</div>
                <div>Status: <strong>${order.status}</strong></div>
            </div>
        </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}

async function _hoCancelOrder(orderId) {
    if (!confirm('Cancel this held order?')) {
        return;
    }
    
    try {
        const response = await fetch(`/held-orders/${orderId}/cancel`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.status === 'ok') {
            alert('Order cancelled');
            _hoRefreshList();
        } else {
            alert(`Error: ${result.message}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// ============================================================================
// Monitoring
// ============================================================================

function _hoStartMonitoring() {
    console.log('Starting held orders monitoring');
    
    // Initial list refresh
    _hoRefreshList();
    
    // Set up periodic checks and status updates
    if (heldOrdersState.refreshInterval) {
        clearInterval(heldOrdersState.refreshInterval);
    }
    
    heldOrdersState.refreshInterval = setInterval(async () => {
        if (heldOrdersState.enabled) {
            try {
                // Check for triggered orders
                const checkResponse = await fetch('/held-orders/check', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                
                const checkResult = await checkResponse.json();
                
                if (checkResult.status === 'ok') {
                    if (checkResult.triggered_orders && checkResult.triggered_orders.length > 0) {
                        console.warn(`Held orders triggered: ${checkResult.triggered_orders.length}`);
                        _hoRefreshList();
                    }
                }
            } catch (error) {
                console.error('Error checking held orders:', error);
            }
            
            // Also refresh list periodically
            _hoRefreshList();
        }
    }, 5000); // Check every 5 seconds
}

function _hoStopMonitoring() {
    console.log('Stopping held orders monitoring');
    
    if (heldOrdersState.refreshInterval) {
        clearInterval(heldOrdersState.refreshInterval);
        heldOrdersState.refreshInterval = null;
    }
}

// ============================================================================
// Initialization
// ============================================================================

function initializeHeldOrders() {
    // Set up event listeners
    const heldOrdersForm = document.getElementById('ho_panel');
    if (heldOrdersForm) {
        // Make sure the form is visible and initialized
        const heldOrdersBtn = document.querySelector('[data-toggle="ho-panel"]');
        if (heldOrdersBtn) {
            heldOrdersBtn.addEventListener('click', () => {
                heldOrdersForm.style.display = heldOrdersForm.style.display === 'none' ? 'block' : 'none';
            });
        }
    }
    
    // Initialize order list container if not present
    if (!document.getElementById('ho_active_orders_list')) {
        const hoBody = document.getElementById('ho_body');
        if (hoBody) {
            const listDiv = document.createElement('div');
            listDiv.id = 'ho_active_orders_list';
            listDiv.style.marginTop = '20px';
            listDiv.style.borderTop = '1px solid #ddd';
            listDiv.style.paddingTop = '10px';
            hoBody.appendChild(listDiv);
        }
    }
}

// Call initialization when document is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeHeldOrders);
} else {
    initializeHeldOrders();
}
