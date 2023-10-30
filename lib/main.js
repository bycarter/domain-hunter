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

// curl -X GET -H "Authorization: sso-key dLYixrwBhad6_GmAhWUm7Tn7PLsTjfoYQCN:8tFe7orDxsPi2zgvxmzJaz" "https://api.godaddy.com/v1/domains/available?domain=example.guru"
// https://api.ote-godaddy.com/
// https://api.godaddy.com/v1/domains/available
async function checkDomain(domainIn) {
  try {
    const res = await axios( {
      method: 'get',
      url: 'https://api.godaddy.com/v1/domains/available',
      params: {
        domain: domainIn,
      },
      headers: {
        "Authorization": `sso-key ${process.env.GD_KEY}:${process.env.GD_SECRET}`,
      },
    })
  console.log(res.data);
  } catch (error) {
    console.log(error);
  }
}
// console.log(`${process.env.GD_KEY}:${process.env.GD_SECRET}`)
checkDomain('google.com');