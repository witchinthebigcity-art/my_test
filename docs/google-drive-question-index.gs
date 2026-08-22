// Однократная настройка описана в docs/GOOGLE_SHEETS_SETUP.md.
// Корневая папка: https://drive.google.com/drive/folders/1CIagfcGHZO_Sdk2G1QysBNg-rX06c_-r

const ROOT_FOLDER_ID = '1CIagfcGHZO_Sdk2G1QysBNg-rX06c_-r';

function doGet() {
  const files = [];
  const root = DriveApp.getFolderById(ROOT_FOLDER_ID);
  collectGradeFolders(root, files);
  files.sort((a, b) => a.grade - b.grade || a.name.localeCompare(b.name, 'ru', {numeric: true}));
  return ContentService
    .createTextOutput(JSON.stringify({updatedAt: new Date().toISOString(), files}))
    .setMimeType(ContentService.MimeType.JSON);
}

function collectGradeFolders(folder, result) {
  const folders = folder.getFolders();
  while (folders.hasNext()) {
    const child = folders.next();
    const match = child.getName().match(/(?:^|\D)(8|9|10|11)(?:\D|$)/);
    if (match) collectFiles(child, Number(match[1]), result);
    else collectGradeFolders(child, result);
  }
}

function collectFiles(folder, grade, result) {
  const files = folder.getFiles();
  while (files.hasNext()) {
    const file = files.next();
    if (!/^image\/(?:jpeg|png|webp)$/.test(file.getMimeType())) continue;
    result.push({
      id: file.getId(),
      name: file.getName(),
      grade,
      mimeType: file.getMimeType(),
      modifiedTime: file.getLastUpdated().toISOString(),
    });
  }
  const nested = folder.getFolders();
  while (nested.hasNext()) collectFiles(nested.next(), grade, result);
}
