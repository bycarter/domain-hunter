const path = require("path");
require("dotenv").config({ path: path.join(__dirname, "../.env") });
const axios = require('axios').default;

const data = require(path.join(__dirname, "data.js"));

const singleDomains = generateDomainArray(data.singles, data.TLDs);
const doubleDomains = generateDomainArray(data.twoCombos, data.TLDs);
const hyphenDomains = generateDomainArray(data.threeComboHyphen, data.TLDs);
const tripleDomains = generateDomainArray(data.threeCombos, data.TLDs);

function generateDomainArray(roots, tlds) {
  let domainArr = [];
  roots.forEach((root) =>
    tlds.forEach((tld) => domainArr.push(root + "." + tld)),
  );
  return domainArr;
}

// curl -X GET -H "Authorization: sso-key 3mM44UdBKAEuj8_R1hFTWCqTc9DZtshWPs6Lp:ZkwK1yD8UV89ryjwV7QvV" "https://api.godaddy.com/v1/domains/available?domain=example.guru"

async function checkDomain(domainIn) {
  try {
    const res = await axios( {
      method: 'get',
      url: 'https://api.godaddy.com/v1/domains/available',
      params: {
        domain: domainIn
      },
      headers: {
        "Authorization": `sso-key ${process.env.GD_KEY}:${process.env.GD_SECRET}`,
      },
    })
  console.log(res);
  } catch (error) {
    console.log(error);
  }
}
// console.log(`${process.env.GD_KEY}:${process.env.GD_SECRET}`)
checkDomain('google.com');