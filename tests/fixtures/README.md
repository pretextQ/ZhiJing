# 测试素材

`scene-loop.webm` 是合成的 3 秒循环背景视频（320×180，VP8/WebM），仅用于
动态背景与主题包导出测试，不含真实拍摄内容。

重新生成需要使用带 libvpx 的 ffmpeg 与 Pillow：把 JPEG 帧通过 `image2pipe`
送入 ffmpeg，再以 libvpx 编码为 WebM。测试只依赖文件存在和浏览器可解码，
不依赖生成脚本。
