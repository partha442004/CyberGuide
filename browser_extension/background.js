// CyberGuide Job Saver - Background Script

// Listen for extension installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('CyberGuide Job Saver installed');
  
  // Set default settings
  chrome.storage.sync.set({
    apiBase: 'https://cyberguide-api.vercel.app',
    autoExtract: true,
    notifications: true
  });
});

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'saveJob') {
    saveJobToAPI(request.data)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    
    return true; // Keep message channel open for async response
  }
  
  if (request.action === 'getSettings') {
    chrome.storage.sync.get(['apiBase', 'autoExtract', 'notifications'], (settings) => {
      sendResponse(settings);
    });
    return true;
  }
});

// Save job to CyberGuide API
async function saveJobToAPI(jobData) {
  const settings = await chrome.storage.sync.get(['apiBase']);
  const apiBase = settings.apiBase || 'https://cyberguide-api.vercel.app';
  
  const response = await fetch(`${apiBase}/api/v1/jobs/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(jobData)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return await response.json();
}

// Context menu for saving jobs
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'saveJob',
    title: 'Save to CyberGuide',
    contexts: ['selection', 'link']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'saveJob') {
    // Open popup with pre-filled data
    chrome.action.openPopup();
  }
});

// Badge update for saved jobs count
async function updateBadge() {
  try {
    const settings = await chrome.storage.sync.get(['apiBase']);
    const apiBase = settings.apiBase || 'https://cyberguide-api.vercel.app';
    
    const response = await fetch(`${apiBase}/api/v1/jobs/?limit=1`);
    if (response.ok) {
      const data = await response.json();
      const count = data.total || 0;
      
      chrome.action.setBadgeText({ text: count.toString() });
      chrome.action.setBadgeBackgroundColor({ color: '#6366f1' });
    }
  } catch (error) {
    console.log('Could not update badge:', error);
  }
}

// Update badge periodically
setInterval(updateBadge, 5 * 60 * 1000); // Every 5 minutes
updateBadge(); // Initial update
