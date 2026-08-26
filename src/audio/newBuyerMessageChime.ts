/**
 * An original three-note chime for a new buyer message.
 *
 * It is synthesized in the browser instead of loading a third-party audio
 * asset, so it has no licensing or download dependency.
 */
let audioContext: AudioContext | null = null;

const getAudioContext = () => {
  if (typeof window === "undefined" || typeof window.AudioContext === "undefined")
    return null;
  audioContext ||= new window.AudioContext();
  return audioContext;
};

export const unlockNewBuyerMessageChime = async () => {
  const context = getAudioContext();
  if (!context) return false;
  if (context.state === "suspended") await context.resume();
  return context.state === "running";
};

export const playNewBuyerMessageChime = async () => {
  try {
    if (!(await unlockNewBuyerMessageChime())) return false;
    const context = getAudioContext();
    if (!context) return false;
    const startAt = context.currentTime + 0.015;

    [
      { frequency: 659.25, offset: 0, duration: 0.22 },
      { frequency: 783.99, offset: 0.16, duration: 0.3 },
      { frequency: 1046.5, offset: 0.42, duration: 0.62 },
    ].forEach(({ frequency, offset, duration }) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      const noteStart = startAt + offset;
      const noteEnd = noteStart + duration;

      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, noteStart);
      gain.gain.setValueAtTime(0.0001, noteStart);
      gain.gain.exponentialRampToValueAtTime(0.1, noteStart + 0.018);
      gain.gain.exponentialRampToValueAtTime(0.0001, noteEnd);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(noteStart);
      oscillator.stop(noteEnd + 0.02);
    });
    return true;
  } catch {
    // Audio can be blocked by browser autoplay policies. Notifications still
    // remain available even when the chime cannot be played.
    return false;
  }
};
