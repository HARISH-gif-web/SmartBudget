/**
 * Expense Tracker - Client JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
  initDarkMode();
  initPasswordToggles();
  initSearchHandler();
  initCalendarInteraction();
});

/* ==========================================================================
   Dark Mode System
   ========================================================================== */
function initDarkMode() {
  const toggleBtns = document.querySelectorAll('.dark-mode-toggle');
  
  // Read saved theme
  const savedTheme = localStorage.getItem('theme');
  const userProfileDark = document.body.dataset.userDark === 'true';

  if (savedTheme) {
    applyTheme(savedTheme);
  } else if (userProfileDark) {
    applyTheme('dark');
  }

  toggleBtns.forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const currentTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);

      // Save to localStorage
      localStorage.setItem('theme', newTheme);

      // Send to server to persist in user profile
      fetch('/toggle-dark-mode/', {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCsrfToken()
        }
      }).catch(err => console.log('Dark mode sync error:', err));
    });
  });
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-bs-theme', theme);
  const darkIcons = document.querySelectorAll('.dark-mode-icon');
  const darkLabels = document.querySelectorAll('.dark-mode-label');

  darkIcons.forEach(icon => {
    if (theme === 'dark') {
      icon.className = 'bi bi-sun-fill text-warning me-2 dark-mode-icon';
    } else {
      icon.className = 'bi bi-moon-stars me-2 dark-mode-icon';
    }
  });

  darkLabels.forEach(label => {
    label.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
  });

  // Re-render chart text if chart exists
  if (window.myDoughnutChart) {
    window.myDoughnutChart.update();
  }
}

function getCsrfToken() {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
}

/* ==========================================================================
   Password Visibility Toggle
   ========================================================================== */
function initPasswordToggles() {
  const toggles = document.querySelectorAll('.toggle-password-btn');
  toggles.forEach(btn => {
    btn.addEventListener('click', function () {
      const targetId = this.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (input) {
        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        const icon = this.querySelector('i');
        if (icon) {
          icon.className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
        }
      }
    });
  });
}

/* ==========================================================================
   Search Input Handler
   ========================================================================== */
function initSearchHandler() {
  const searchInput = document.getElementById('global-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const query = searchInput.value.trim();
        if (query) {
          window.location.href = `/expenses/?q=${encodeURIComponent(query)}`;
        }
      }
    });
  }
}

/* ==========================================================================
   Calendar Day Interaction
   ========================================================================== */
function initCalendarInteraction() {
  const dayCells = document.querySelectorAll('.calendar-day-cell:not(.empty-day)');
  const detailContainer = document.getElementById('calendar-day-details');
  const detailDateHeader = document.getElementById('calendar-detail-date');
  const detailExpensesList = document.getElementById('calendar-detail-expenses');
  const detailTotal = document.getElementById('calendar-detail-total');

  if (!dayCells.length || !detailExpensesList) return;

  let dayDataMap = {};
  const dataScript = document.getElementById('calendar-data-json');
  if (dataScript) {
    try {
      dayDataMap = JSON.parse(dataScript.textContent);
    } catch (e) {
      console.error('Failed to parse calendar json:', e);
    }
  }

  dayCells.forEach(cell => {
    cell.addEventListener('click', function () {
      dayCells.forEach(c => c.classList.remove('is-selected'));
      this.classList.add('is-selected');

      const dateStr = this.getAttribute('data-date');
      const formattedDate = this.getAttribute('data-formatted-date');
      const expenses = dayDataMap[dateStr] || [];

      if (detailDateHeader) {
        detailDateHeader.textContent = `Expenses on ${formattedDate}`;
      }

      detailExpensesList.innerHTML = '';
      let sum = 0;

      if (expenses.length === 0) {
        detailExpensesList.innerHTML = `
          <div class="text-center py-4 text-muted">
            <i class="bi bi-calendar-check fs-2 mb-2 d-block"></i>
            <p class="mb-0">No expenses recorded on this day.</p>
          </div>
        `;
      } else {
        expenses.forEach(exp => {
          sum += exp.amount;
          const item = document.createElement('div');
          item.className = 'd-flex align-items-center justify-content-between p-2.5 mb-2 rounded bg-hover';
          item.innerHTML = `
            <div class="d-flex align-items-center gap-2">
              <span class="fs-5">${exp.icon}</span>
              <div>
                <div class="fw-semibold text-main">${exp.notes || exp.category}</div>
                <small class="text-muted">${exp.category}</small>
              </div>
            </div>
            <div class="text-end">
              <span class="fw-bold text-main">₹${exp.amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
            </div>
          `;
          detailExpensesList.appendChild(item);
        });
      }

      if (detailTotal) {
        detailTotal.textContent = `₹${sum.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      }
    });
  });
}
