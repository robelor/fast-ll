# Fast-ll

Fast-ll is a LL-DASH web server. It handles segment PUT and GET request so request can arrive even
before the actual segment has arrived. Then, it uses HTTP chunked transfer to server segments as
they arrive.

## Fast-ll request diagram

```mermaid
sequenceDiagram
    autonumber
    participant FFmpeg
    participant Server
    participant Client
    FFmpeg->>Server: PUT manifest.mpd
    FFmpeg->>Server: PUT init.mp4
    FFmpeg->>Server: PUT segment01.mp4
    FFmpeg->>Server: PUT segment02.mp4
    FFmpeg->>Server: ...
    Client->>Server: GET manifest.mpd
    Client->>Server: GET init.mp4
    loop 
        Client->>Server: GET segmentY.mp4
        FFmpeg->>Server: PUT segmentX.mp4
    end
    
```