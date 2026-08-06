# CyberGuide Job Saver - Installation Guide

## Quick Install (Developer Mode)

### Step 1: Download the Extension

1. Go to your CyberGuide project folder
2. Navigate to `browser_extension/` folder

### Step 2: Open Chrome Extensions Page

1. Open Google Chrome
2. Type `chrome://extensions/` in the address bar
3. Press Enter

### Step 3: Enable Developer Mode

1. Look for "Developer mode" toggle in the top right corner
2. Click to enable it

### Step 4: Load the Extension

1. Click "Load unpacked" button (top left)
2. Navigate to and select the `browser_extension` folder
3. Click "Select Folder"

### Step 5: Pin the Extension

1. Click the puzzle piece icon (Extensions) in Chrome toolbar
2. Find "CyberGuide Job Saver"
3. Click the pin icon to pin it to toolbar

## Usage

### Method 1: Floating Button

1. Visit any job posting (LinkedIn, Indeed, Naukri, etc.)
2. Look for the purple "Save to CyberGuide" button in bottom right
3. Click it to open the save dialog
4. Review auto-filled information
5. Click "Save Job"

### Method 2: Extension Icon

1. Click the CyberGuide icon in your toolbar
2. Fill in job details (or let auto-extraction fill them)
3. Click "Save Job"

### Method 3: Right-click Menu

1. Select job title or company name
2. Right-click and choose "Save to CyberGuide"

## Supported Job Boards

- LinkedIn
- Indeed
- Glassdoor
- Naukri
- Internshala
- TimesJobs
- Hired
- AngelList/Wellfound
- Any other website!

## Troubleshooting

### Extension not working?

1. Reload the extension: Go to `chrome://extensions/` and click refresh icon
2. Check if API is accessible: Visit https://cyberguide-api.vercel.app/health

### Auto-extraction not working?


1. Some job boards use dynamic loading
2. Wait for page to fully load before clicking save
3. You can always manually enter job details

## API Configuration

The extension connects to: `https://cyberguide-api.vercel.app`

No API key required for basic usage.
