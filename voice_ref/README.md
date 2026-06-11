# GPT-SoVITS Voice References

Place your target reference audio files in this directory. 

### Requirements:
- **Format**: `.wav` file
- **Length**: Approximately 3 to 10 seconds (optimal for GPT-SoVITS `api_v2.py` voice cloning)
- **Quality**: Clear, mono/stereo audio without background noise or music.

Configure your active reference audio in `config.py` by setting `REFER_WAV_PATH` (and match the `REFER_PROMPT_TEXT` and `REFER_PROMPT_LANG` to what is spoken in the audio file).
