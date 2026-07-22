// GENERATED from tests/fake_hardware.py - device bitmap8 metrics
export const BITMAP8_W = {"a": 4, "b": 4, "c": 4, "d": 4, "e": 4, "f": 4, "g": 4, "h": 4, "i": 3, "j": 4, "k": 4, "l": 3, "m": 5, "n": 4, "o": 4, "p": 4, "q": 4, "r": 4, "s": 4, "t": 4, "u": 4, "v": 4, "w": 5, "x": 4, "y": 4, "z": 4, "A": 4, "B": 4, "C": 4, "D": 4, "E": 4, "F": 4, "G": 4, "H": 4, "I": 3, "J": 4, "K": 4, "L": 4, "M": 5, "N": 4, "O": 4, "P": 4, "Q": 4, "R": 4, "S": 4, "T": 5, "U": 4, "V": 4, "W": 5, "X": 4, "Y": 4, "Z": 4, "0": 4, "1": 3, "2": 4, "3": 4, "4": 4, "5": 4, "6": 4, "7": 4, "8": 4, "9": 4, " ": 3, ".": 2, ",": 2, ":": 1, ";": 2, "!": 1, "?": 4, "(": 3, ")": 3, "+": 3, "-": 3, "/": 4, "*": 3, "<": 3, ">": 3, "=": 3, "%": 4, "&": 4, "'": 1, "\"": 3};
export function measureText(s, scale = 1) {
  s = String(s);
  if (!s.length) return 0;
  let w = 0;
  for (const c of s) w += (BITMAP8_W[c] ?? 4);
  return (w + s.length - 1) * scale;
}