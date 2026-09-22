import { IPTV_INSTRUCTIONS } from "@/lib/iptv";

export function IptvAccess({
  playlistUrl,
  instructions,
}: {
  playlistUrl: string;
  instructions?: string | null;
}) {
  const text = instructions || IPTV_INSTRUCTIONS;
  return (
    <div className="iptv-access">
      <div className="creds">
        <div className="row">
          <span>Посилання на плейлист</span>
          <b>
            <a href={playlistUrl} target="_blank" rel="noopener noreferrer" style={{ wordBreak: "break-all" }}>
              {playlistUrl}
            </a>
          </b>
        </div>
      </div>
      <div className="iptv-instructions" style={{ marginTop: 14, whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
        {text}
      </div>
    </div>
  );
}
