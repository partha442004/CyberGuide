// CyberGuide Job Saver - Popup Script

const API_BASE = 'https://cyberguide-api.vercel.app';

// DOM Elements
const jobForm = document.getElementById('job-form');
const successMessage = document.getElementById('success-message');
const errorMessage = document.getElementById('error-message');
const errorText = document.getElementById('error-text');
const saveBtn = document.getElementById('save-btn');
const cancelBtn = document.getElementById('cancel-btn');
const viewJobsBtn = document.getElementById('view-jobs-btn');

// Form Elements
const titleInput = document.getElementById('job-title');
const companyInput = document.getElementById('company');
const urlInput = document.getElementById('url');
const locationInput = document.getElementById('location');
const salaryInput = document.getElementById('salary');
const tagsInput = document.getElementById('tags');
const notesInput = document.getElementById('notes');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Try to extract job info from current page
  await extractJobInfo();
  
  // Set up event listeners
  setupEventListeners();
});

// Extract job info from current page
async function extractJobInfo() {
  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (tab) {
      // Try to extract job info using content script
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractJobData
      });
      
      if (results && results[0] && results[0].result) {
        const jobData = results[0].result;
        
        // Fill form with extracted data
        if (jobData.title) titleInput.value = jobData.title;
        if (jobData.company) companyInput.value = jobData.company;
        if (jobData.url) urlInput.value = jobData.url;
        if (jobData.location) locationInput.value = jobData.location;
        if (jobData.salary) salaryInput.value = jobData.salary;
        if (jobData.tags) tagsInput.value = jobData.tags.join(', ');
      }
    }
  } catch (error) {
    console.log('Could not extract job info:', error);
  }
}

// Function to extract job data from page (runs in content script context)
function extractJobData() {
  const data = {
    title: '',
    company: '',
    url: window.location.href,
    location: '',
    salary: '',
    tags: []
  };
  
  // Try common job board selectors
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
      '[class*="location"]',
      '.job-location-shipping'
    ],
    salary: [
      '.salary',
      '.compensation',
      '[class*="salary"]',
      '.job-salary'
    ]
  };
  
  // Extract title
  for (const selector of selectors.title) {
    const element = document.querySelector(selector);
    if (element) {
      data.title = element.textContent.trim();
      break;
    }
  }
  
  // Extract company
  for (const selector of selectors.company) {
    const element = document.querySelector(selector);
    if (element) {
      data.company = element.textContent.trim();
      break;
    }
  }
  
  // Extract location
  for (const selector of selectors.location) {
    const element = document.querySelector(selector);
    if (element) {
      data.location = element.textContent.trim();
      break;
    }
  }
  
  // Extract salary
  for (const selector of selectors.salary) {
    const element = document.querySelector(selector);
    if (element) {
      data.salary = element.textContent.trim();
      break;
    }
  }
  
  // Extract tags/keywords
  const metaKeywords = document.querySelector('meta[name="keywords"]');
  if (metaKeywords) {
    data.tags = metaKeywords.content.split(',').map(t => t.trim()).slice(0, 5);
  }
  
  // Extract from page title if no title found
  if (!data.title) {
    const pageTitle = document.title;
    // Remove common suffixes
    data.title = pageTitle
      .replace(/ - LinkedIn/g, '')
      .replace(/ \| Indeed/g, '')
      .replace(/ - Glassdoor/g, '')
      .trim();
  }
  
  return data;
}

// Setup event listeners
function setupEventListeners() {
  // Save button
  saveBtn.addEventListener('click', saveJob);
  
  // Cancel button
  cancelBtn.addEventListener('click', () => {
    window.close();
  });
  
  // View jobs button
  viewJobsBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: `${API_BASE}/dashboard` });
    window.close();
  });
}

// Save job to CyberGuide
async function saveJob() {
  const title = titleInput.value.trim();
  const company = companyInput.value.trim();
  
  if (!title || !company) {
    showError('Please enter job title and company');
    return;
  }
  
  // Show loading state
  saveBtn.disabled = true;
  saveBtn.querySelector('.btn-text').style.display = 'none';
  saveBtn.querySelector('.btn-loading').style.display = 'inline';
  
  try {
    const jobData = {
      title: title,
      company: company,
      url: urlInput.value.trim() || '',
      location: locationInput.value.trim() || '',
      salary_min: parseSalaryMin(salaryInput.value),
      salary_max: parseSalaryMax(salaryInput.value),
      tags: tagsInput.value.split(',').map(t => t.trim()).filter(t => t),
      description: notesInput.value.trim() || '',
      source: 'browser_extension'
    };
    
    const response = await fetch(`${API_BASE}/api/v1/jobs/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(jobData)
    });
    
    if (response.ok) {
      showSuccess();
    } else {
      const error = await response.text();
      showError(error || 'Failed to save job');
    }
  } catch (error) {
    showError('Network error. Please try again.');
    console.error('Save error:', error);
  } finally {
    // Reset button state
    saveBtn.disabled = false;
    saveBtn.querySelector('.btn-text').style.display = 'inline';
    saveBtn.querySelector('.btn-loading').style.display = 'none';
  }
}

// Parse salary values
function parseSalaryMin(salaryStr) {
  if (!salaryStr) return null;
  
  // Remove currency symbols and parse
  const numbers = salaryStr.replace(/[₹$€£,]/g, '').match(/\d+/g);
  if (numbers && numbers.length >= 1) {
    return parseInt(numbers[0]);
  }
  return null;
}

function parseSalaryMax(salaryStr) {
  if (!salaryStr) return null;
  
  const numbers = salaryStr.replace(/[₹$€£,]/g, '').match(/\d+/g);
  if (numbers && numbers.length >= 2) {
    return parseInt(numbers[1]);
  } else if (numbers && numbers.length === 1) {
    return parseInt(numbers[0]);
  }
  return null;
}

// Show success message
function showSuccess() {
  jobForm.style.display = 'none';
  successMessage.style.display = 'block';
}

// Show error message
function showError(message) {
  errorText.textContent = message;
  errorMessage.style.display = 'block';
  
  // Auto-hide after 5 seconds
  setTimeout(() => {
    errorMessage.style.display = 'none';
  }, 5000);
}
