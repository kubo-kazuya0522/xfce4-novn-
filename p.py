@kubo-kazuya0522 ➜ ~/デスクトップ $ pulseaudio -k
sleep 2
pulseaudio --start
@kubo-kazuya0522 ➜ ~/デスクトップ $ sleep 2
@kubo-kazuya0522 ➜ ~/デスクトップ $ pulseaudio --start
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl unload-module module-null-sink
pactl unload-module module-null@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl unload-module module-null-sink
pactl unlモジュールのアンロードに失敗: モジュール module-null-sink はロードされていません
oad-modu@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl unload-module module-null-sink
pactl unモジュールのアンロードに失敗: モジュール module-null-sink はロードされていません
load-module module-n@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl unload-module module-null-sink
モジュールのアンロードに失敗: モジュール module-null-sink はロードされていません
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl list short sinks
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl load-module module-null-sink sink_name=webrtc
19
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl set-default-sink webrtc
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl info | grep "Default Sink"
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl list short sinks
1	webrtc	module-null-sink.c	s16le 2ch 44100Hz	IDLE
@kubo-kazuya0522 ➜ ~/デスクトップ $ paplay --device=webrtc /usr/share/sounds/freedesktop/stereo/complete.oga
@kubo-kazuya0522 ➜ ~/デスクトップ $ pactl list short sink-inputs
@kubo-kazuya0522 ➜ ~/デスクトップ $ 

