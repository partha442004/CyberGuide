// CyberGuide Job Saver - Content Script

// Add floating save button to job pages
(function() {
  'use strict';
  
  // Check if we're on a job page
  function isJobPage() {
    const url = window.location.href.toLowerCase();
    const title = document.title.toLowerCase();
    
    const jobIndicators = [
      'job', 'career', 'position', 'opening', 'vacancy',
      'apply', 'hiring', 'recruitment'
    ];
    
    return jobIndicators.some(indicator => 
      url.includes(indicator) || title.includes(indicator)
    );
  }
  
  // Create floating save button
  function createSaveButton() {
    const button = document.createElement('div');
    button.id = 'cyberguide-save-btn';
    button.innerHTML = `
      <div class="cyberguide-btn-content">
        <svg class="cyberguide-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
        </svg>
        <span>Save to CyberGuide</span>
      </div>
    `;
    
    button.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999999;
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      color: white;
      padding: 12px 20px;
      border-radius: 50px;
      cursor: pointer;
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.3s ease;
    `;
    
    button.onmouseover = function() {
      this.style.transform = 'translateY(-2px)';
      this.style.boxShadow = '0 6px 20px rgba(99, 102, 241, 0.5)';
    };
    
    button.onmouseout = function() {
      this.style.transform = 'translateY(0)';
      this.style.boxShadow = '0 4px 15px rgba(99, 102, 241, 0.4)';
    };
    
    button.onclick = function() {
      // Send message to background script to open popup
      chrome.runtime.sendMessage({ action: 'openPopup' });
    };
    
    document.body.appendChild(button);
  }
  
  // Auto-extract job info from page
  function extractJobInfo() {
    const jobData = {
      title: '',
      company: '',
      location: '',
      salary: '',
      url: window.location.href
    };
    
    // Common selectors for job boards
    const selectors = {
      title: [
        'h1.job-title',
        'h1[data-job-id]',
        '.job-title',
        '.posting-headline h2',
        'h1.top-heading',
        '[class*="jobTitle"]',
        'h1'
      ],
      company: [
        '.company-name',
        '.employer-name',
        '.company',
        '[class*="company"]',
        'h2.company-name'
      ],
      location: [
        '.job-location',
        '.location',
        '[class*="location"]'
      ],
      salary: [
        '.salary',
        '.compensation',
        '[class*="salary"]'
      ]
    };
    
    // Extract data using selectors
    for (const [key, selectorList] of Object.entries(selectors)) {
      for (const selector of selectorList) {
        const element = document.querySelector(selector);
        if (element) {
          jobData[key] = element.textContent.trim();
          break;
        }
      }
    }
    
    return jobData;
  }
  
  // Initialize
  if (isJobPage()) {
    createSaveButton();
    
    // Store extracted job info for popup
    const jobInfo = extractJobInfo();
    if (jobInfo.title || jobInfo.company) {
      chrome.storage.local.set({ currentJob: jobInfo });
    }
  }
})();
