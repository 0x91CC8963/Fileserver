## Fileserver
Current notes for my actual localhost fileserver I run.  
It serves various purposes but the basic idea is that all of the important stuff happens on a raid device.  
So as long as 1 device has a working pool the OS can come and go.  

## Key
`/fileops/` -> Scripts that work with files (bulk utilities)  
`/webops/` -> Scripts that work with web operations (like scraping)

## Layout
```
00-incoming/
10-data/
    Documents/
    Media/
    Projects/
20-git/
    Fileserver/
    DISK_GEN/
    Flask-FTP-Server/ 
30-services/
    jellyfin/ 
40-applications/
    website/ 
50-system/
60-archives/
    fonts/
    games/
    webrips/ 
90-backups/ 
99-temp/ 
```
