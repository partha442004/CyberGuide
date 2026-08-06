# CyberGuide Job Saver - Browser Extension

A Chrome extension that lets you save jobs from any website to CyberGuide with one click.

## Features

- **One-click job saving** - Save jobs from LinkedIn, Indeed, Glassdoor, and any other job board
- **Auto-extraction** - Automatically extracts job title, company, location, and other details
- **Floating save button** - Appears on job pages for quick saving
- **Right-click menu** - Save jobs by selecting text and right-clicking
- **Badge counter** - Shows total saved jobs on the extension icon

## Installation

### From Chrome Web Store (Coming Soon)
1. Visit the Chrome Web Store
2. Search for "CyberGuide Job Saver"
3. Click "Add to Chrome"

### Manual Installation (Developer Mode)
1. Download or clone this repository
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode" in the top right
4. Click "Load unpacked"
5. Select the `browser_extension` folder

## Usage

### Method 1: Floating Button
1. Navigate to any job posting
2. Click the purple "Save to CyberGuide" button in the bottom right
3. The popup will open with pre-filled job details
4. Review and edit the information
5. Click "Save Job"

### Method 2: Extension Icon
1. Click the CyberGuide icon in your browser toolbar
2. The popup will open
3. Fill in the job details (or let auto-extraction fill them)
4. Click "Save Job"

### Method 3: Right-click Menu
1. Select job title or company name on a job page
2. Right-click and select "Save to CyberGuide"
3. The popup will open with the selected text

## Supported Job Boards

The extension works with all job boards, including:
- LinkedIn
- Indeed
- Glassdoor
- Naukri
- Internshala
- TimesJobs
- And any other website!

## Configuration

Click the extension icon and then the settings gear to configure:
- **API Base URL**: Your CyberGuide API endpoint
- **Auto-extract**: Enable/disable automatic job info extraction
- **Notifications**: Enable/disable save confirmations

## Development

### Project Structure
```
browser_extension/
├── manifest.json       # Extension configuration
├── popup.html         # Popup UI
├── popup.css          # Popup styles
├── popup.js           # Popup logic
├── background.js      # Background service worker
├── content.js         # Content script for page injection
├── content.css        # Content script styles
├── icons/             # Extension icons
└── README.md          # This file
```

### Building
No build step required. The extension uses plain HTML, CSS, and JavaScript.

### Testing
1. Load the extension in developer mode
2. Navigate to a job board
3. Click the save button
4. Verify the job is saved to your CyberGuide account

## API Integration

The extension communicates with the CyberGuide API:
- `POST /api/v1/jobs/` - Save a new job
- `GET /api/v1/jobs/` - Get saved jobs count

## Permissions

- `activeTab` - Access the current tab for job extraction
- `storage` - Store extension settings
- `scripting` - Inject content scripts for job extraction
- `<all_urls>` - Work on all websites

## Support

For issues or feature requests, please visit:
- GitHub: https://github.com/partha442004/CyberGuide
- Email: parthasarathi442004@gmail.com

## License

MIT License - see LICENSE file for details
