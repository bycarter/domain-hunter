const chars = "abcdefghijklmnopqrstuvwxyz1234567890";
const singles = chars.split("");
const twoCombos = [];
const threeCombos = [];
const threeComboHyphen = [];
const TLDs = [
  "io",
  "ai",
  "co",
  "me",
  "ly",
  "tv",
  "cc",
  "ws",
  "gg",
  "is",
  "so",
  "us",
  "vc",
  "to",
  "art",
  "dev",
  "lol",
  "icu",
  "one",
  "tech",
  "ink",
  "app",
  "bot",
  "onl",
  "net",
  "bet",
  "day",
  "fit",
];

for (let i = 0; i < chars.length; i++) {
  twoCombos.push(chars[i] + chars[i]);
  threeComboHyphen.push(chars[i] + "-" + chars[i]);

  threeCombos.push(chars[i] + chars[i] + chars[i]);

  for (let j = i + 1; j < chars.length; j++) {
    twoCombos.push(chars[i] + chars[j]);
    twoCombos.push(chars[j] + chars[i]);
    threeComboHyphen.push(chars[i] + "-" + chars[j]);
    threeComboHyphen.push(chars[j] + "-" + chars[i]);

    threeCombos.push(chars[i] + chars[i] + chars[j]);
    threeCombos.push(chars[i] + chars[j] + chars[i]);
    threeCombos.push(chars[j] + chars[i] + chars[i]);
    threeCombos.push(chars[i] + chars[j] + chars[j]);
    threeCombos.push(chars[j] + chars[i] + chars[j]);
    threeCombos.push(chars[j] + chars[j] + chars[i]);

    for (let k = j + 1; k < chars.length; k++) {
      threeCombos.push(chars[i] + chars[j] + chars[k]);
      threeCombos.push(chars[i] + chars[k] + chars[j]);

      threeCombos.push(chars[j] + chars[k] + chars[i]);
      threeCombos.push(chars[j] + chars[i] + chars[k]);

      threeCombos.push(chars[k] + chars[i] + chars[j]);
      threeCombos.push(chars[k] + chars[j] + chars[i]);

      // threeCombos.push(chars[i] + chars[i] + chars[k]);
      // threeCombos.push(chars[i] + chars[k] + chars[i]);
      // threeCombos.push(chars[k] + chars[i] + chars[i]);
      // threeCombos.push(chars[i] + chars[k] + chars[k]);
      // threeCombos.push(chars[k] + chars[i] + chars[k]);
      // threeCombos.push(chars[k] + chars[k] + chars[i]);
    }
  }
}

function testTwo() {
  for (let i = 0; i < twoCombos.length; i++) {
    if (
      twoCombos.slice(0, i).includes(twoCombos[i]) ||
      twoCombos.slice(i + 1, twoCombos.length).includes(twoCombos[i])
    ) {
      console.log(`duplicate: ${twoCombos[i]}`);
    }
  }
}
function testThree() {
  for (let i = 0; i < threeCombos.length; i++) {
    if (
      threeCombos.slice(0, i).includes(threeCombos[i]) ||
      threeCombos.slice(i + 1, threeCombos.length).includes(threeCombos[i])
    ) {
      console.log(`duplicate: ${twoCombos[i]}`);
    }
  }
}

function testHyph() {
  for (let i = 0; i < threeComboHyphen.length; i++) {
    if (
      threeComboHyphen.slice(0, i).includes(threeComboHyphen[i]) ||
      threeComboHyphen
        .slice(i + 1, threeComboHyphen.length)
        .includes(threeComboHyphen[i])
    ) {
      console.log(`duplicate: ${threeComboHyphen[i]}`);
    }
  }
}

module.exports = {
  singles,
  twoCombos,
  threeCombos,
  threeComboHyphen,
  TLDs,
};
