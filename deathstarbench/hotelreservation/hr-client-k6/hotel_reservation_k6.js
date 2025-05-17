import http from 'k6/http';
import { check, sleep } from 'k6';

const url = "http://frontend.default.svc.cluster.local:5000";

export const options = {
    scenarios: {
        open_model: {
        executor: 'constant-arrival-rate',
        rate:3000,
        timeUnit: '1s',
        duration: '1m',
        preAllocatedVUs:500000 ,
        maxVUs: 5000000,
        },
    },
};

function getUser() {
  const id = Math.floor(Math.random() * 501);
  const userName = `Cornell_${id}`;
  let passWord = "";
  for (let i = 0; i < 10; i++) {
    passWord += id.toString();
  }
  return { userName, passWord };
}

function searchHotel() {
  const inDate = Math.floor(Math.random() * (24 - 9 + 1)) + 9;
  const outDate = Math.floor(Math.random() * (24 - inDate)) + inDate + 1;

  const inDateStr = inDate <= 9 ? `2015-04-0${inDate}` : `2015-04-${inDate}`;
  const outDateStr = outDate <= 9 ? `2015-04-0${outDate}` : `2015-04-${outDate}`;

  const lat = 38.0235 + (Math.floor(Math.random() * 482) - 240.5) / 1000.0;
  const lon = -122.095 + (Math.floor(Math.random() * 326) - 157.0) / 1000.0;

  const method = "GET";
  const path = `${url}/hotels?inDate=${inDateStr}&outDate=${outDateStr}&lat=${lat}&lon=${lon}`;

  const headers = {};
  return http.get(path)
//   return { method, path, headers };
}

function recommend() {
  const coin = Math.random();
  let reqParam = "";
  if (coin < 0.33) {
    reqParam = "dis";
  } else if (coin < 0.66) {
    reqParam = "rate";
  } else {
    reqParam = "price";
  }

  const lat = 38.0235 + (Math.floor(Math.random() * 482) - 240.5) / 1000.0;
  const lon = -122.095 + (Math.floor(Math.random() * 326) - 157.0) / 1000.0;

  const method = "GET";
  const path = `${url}/recommendations?require=${reqParam}&lat=${lat}&lon=${lon}`;
  const headers = {};
  return http.get(path);
//   return { method, path, headers };
}

function reserve() {
  const inDate = Math.floor(Math.random() * (23 - 9 + 1)) + 9;
  const outDate = inDate + Math.floor(Math.random() * 5) + 1;

  const inDateStr = inDate <= 9 ? `2015-04-0${inDate}` : `2015-04-${inDate}`;
  const outDateStr = outDate <= 9 ? `2015-04-0${outDate}` : `2015-04-${outDate}`;
  
  const lat = 38.0235 + (Math.floor(Math.random() * 482) - 240.5) / 1000.0;
  const lon = -122.095 + (Math.floor(Math.random() * 326) - 157.0) / 1000.0;

  const hotelId = Math.floor(Math.random() * 80) + 1;
  const { userName, passWord } = getUser();
  const custName = userName;

  const numRoom = "1";

//   const method = "POST";
  const path = `${url}/reservation?inDate=${inDateStr}&outDate=${outDateStr}&lat=${lat}&lon=${lon}&hotelId=${hotelId}&customerName=${custName}&username=${userName}&password=${passWord}&number=${numRoom}`;
//   const headers = {};
  return http.post(path);
}

function userLogin() {
  const { userName, passWord } = getUser();
  const method = "POST";
  const path = `${url}/user?username=${userName}&password=${passWord}`;
  const headers = {};
  http.post(path)
  return http.post(path);
}

function request() {
  const searchRatio = 0.6;
  const recommendRatio = 0.39;
  const userRatio = 0.005;
  const reserveRatio = 0.005;

  const coin = Math.random();
  if (coin < searchRatio) {
    return searchHotel();
  } else if (coin < searchRatio + recommendRatio) {
    return recommend();
  } else if (coin < searchRatio + recommendRatio + userRatio) {
    return userLogin();
  } else {
    return reserve();
  }
}
export default function() {
    // const res = http.get('https://test-api.k6.io/');
    // const res = http.get('https://ms1024.utah.cloudlab.us:8443')
    const res = request()
    check(res, {
        'status is 200': (r) => r.status === 200,
        'protocol is HTTP/2': (r) => r.proto === 'HTTP/2.0',
      });
}