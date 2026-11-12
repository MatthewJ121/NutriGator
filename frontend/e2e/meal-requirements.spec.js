import { test, expect } from '@playwright/test';

const TODAY = '2026-11-12';
const YESTERDAY = '2026-11-11';
const seed = () => [
  { meal_id: 2, food_name: 'Later breakfast', consumed_at: `${TODAY}T15:00:00Z`, calories: 200, protein: 0, carbs: -1 },
  { meal_id: 1, food_name: 'Early breakfast', consumed_at: `${TODAY}T13:00:00Z`, calories: 100.5, protein: 2.5, carbs: -1 },
  { meal_id: 3, food_name: 'Yesterday meal', consumed_at: `${YESTERDAY}T17:00:00Z`, calories: 300, protein: 5 },
];

async function setup(page, initial = seed()) {
  const state = { rows: initial, requests: [], usdaRequests: [], expired: null, nextId: 100 };
  await page.clock.install({ time: new Date(`${TODAY}T17:00:00Z`) });
  await page.route(/^http:\/\/(localhost|127\.0\.0\.1):8000\//, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (method === 'OPTIONS') return route.fulfill({ status: 204 });
    state.requests.push({ path, method, body: request.postDataJSON() });
    if (state.expired === `${method} ${path}` || state.expired === method) return route.fulfill({status:401,json:{detail:'Expired session'}});
    if (path === '/auth/login') return route.fulfill({json:{user:{id:'audit-user',email:'audit@example.com',name:'Audit'}}});
    if (path.startsWith('/api/goals/')) return route.fulfill({json:{goals:[]}});
    if (path.startsWith('/api/meals/') && method === 'GET') {
      const day = path.split('/').pop();
      const rows = state.rows.filter(row => new Date(row.consumed_at).toLocaleDateString('en-CA',{timeZone:'America/New_York'}) === day);
      return rows.length ? route.fulfill({json:rows}) : route.fulfill({status:204});
    }
    if (path === '/api/meals' && method === 'POST') {
      const body = request.postDataJSON();
      const row = { ...body, meal_id: body.meal_id ?? state.nextId++ };
      state.rows = [...state.rows.filter(item => item.meal_id !== row.meal_id), row];
      return route.fulfill({json:row});
    }
    if (path.startsWith('/api/meals/') && method === 'DELETE') {
      state.rows = state.rows.filter(row => row.meal_id !== Number(path.split('/').pop()));
      return route.fulfill({status:204});
    }
    return route.fulfill({status:404,json:{detail:'Unmocked endpoint'}});
  });
  await page.route('https://api.nal.usda.gov/**', async route => {
    const url = new URL(route.request().url());
    state.usdaRequests.push({query:url.searchParams.get('query'),page:url.searchParams.get('pageNumber')});
    if (url.searchParams.get('query') === 'no results') return route.fulfill({json:{foods:[],totalPages:0}});
    const second = url.searchParams.get('pageNumber') === '2';
    return route.fulfill({json:{totalPages:2,foods:[{fdcId:second ? 2 : 1,description:second ? 'Second page food' : 'Rice & beans',servingSize:30,servingSizeUnit:'g',foodNutrients:[{nutrientId:1008,value:200},{nutrientId:1003,value:0}]}]}});
  });
  await page.goto('/');
  await page.getByLabel('Email',{exact:true}).fill('audit@example.com');
  await page.getByLabel('Password',{exact:true}).fill('test-password');
  await page.getByRole('button',{name:'Log In',exact:true}).click();
  await expect(page.getByRole('button',{name:'Log breakfast',exact:true})).toBeVisible();
  await expect.poll(() => state.requests.some(r => r.method === 'GET' && r.path === `/api/meals/${TODAY}`)).toBeTruthy();
  await expect(page.locator('.logItemName')).toHaveCount(initial.filter(row => row.consumed_at.startsWith(TODAY)).length);
  return state;
}

async function edit(page, name = 'Early breakfast') {
  await page.locator('.logItemName').filter({hasText:name}).click();
  await page.getByRole('button',{name:'Edit',exact:true}).click();
}

async function foodSearch(page, query = 'rice & beans') {
  await page.getByRole('button',{name:'Log breakfast',exact:true}).click();
  await page.getByLabel('Search food',{exact:true}).fill(query);
  await expect(page.getByRole('button',{name:'Search',exact:true})).toHaveCount(0);
}

test('normal login: date, ordering, nutrient details, scrolling and history', async ({page}) => {
  const state = await setup(page);
  await expect(page.getByText('Demo Mode — Frontend Testing Only')).toHaveCount(0);
  await expect(page.locator('.logDateTitle')).toContainText('November 12, 2026');
  await expect(page.getByRole('button',{name:'Next →'})).toBeDisabled();
  await expect(page.locator('.logItemName')).toHaveText([/Early breakfast/,/Later breakfast/]);
  await page.locator('.logItemName').filter({hasText:'Later breakfast'}).click();
  const detail = page.getByRole('dialog',{name:'Meal details'});
  await expect(detail).toContainText('Protein0g');
  await expect(detail).not.toContainText('Carbs');
  await expect(detail).toContainText('10:00');
  await expect(detail).toContainText('November 12, 2026');
  await page.getByRole('button',{name:'Close',exact:true}).click();
  expect(await page.locator('.logItemList').first().evaluate(el => getComputedStyle(el).overflowY)).toBe('auto');
  await page.getByRole('button',{name:'← Prev'}).click();
  await expect(page.locator('.logDateTitle')).toContainText('November 11, 2026');
  await expect(page.locator('.logItemName')).toHaveText([/Yesterday meal/]);
  await page.getByRole('button',{name:'← Prev'}).click();
  await expect(page.locator('.logItemName')).toHaveCount(0);
  await page.getByRole('button',{name:'Today',exact:true}).click();
  await expect(page.locator('.logItemName')).toHaveCount(2);
  expect(state.requests.some(r => r.path === `/api/meals/${YESTERDAY}`)).toBeTruthy();
});

test('cancel changes nothing; save edits food, date, time and nutrients with omitted untracked fields', async ({page}) => {
  const state = await setup(page);
  await edit(page);
  await page.getByLabel('Food',{exact:true}).fill('Cancelled');
  await page.getByLabel('Calories',{exact:true}).fill('900');
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  expect(state.requests.filter(r => r.method === 'POST' && r.path === '/api/meals')).toHaveLength(0);
  expect(state.rows.find(r => r.meal_id === 1).food_name).toBe('Early breakfast');
  await page.getByRole('button',{name:'Edit',exact:true}).click();
  await page.getByLabel('Food',{exact:true}).fill('Updated food');
  await page.getByLabel('Date',{exact:true}).fill(YESTERDAY);
  await page.getByLabel('Time',{exact:true}).fill('18:30:00');
  await page.getByLabel('Calories',{exact:true}).fill('');
  await page.getByLabel('Protein (g)',{exact:true}).fill('0');
  await page.getByRole('button',{name:'Save meal'}).click();
  await expect(page.locator('.logItemName').filter({hasText:'Early breakfast'})).toHaveCount(0);
  const body = state.requests.find(r => r.method === 'POST' && r.path === '/api/meals').body;
  expect(body).toEqual({meal_id:1,meal_type:'breakfast',food_name:'Updated food',consumed_at:`${YESTERDAY}T23:30:00.000Z`,protein:0});
  await page.getByRole('button',{name:'← Prev'}).click();
  await page.locator('.logItemName').filter({hasText:'Updated food'}).click();
  await expect(page.getByRole('dialog',{name:'Meal details'})).toContainText('Protein0g');
  await expect(page.getByRole('dialog',{name:'Meal details'})).not.toContainText('Calories');
});

test('negative and nonnumeric nutrients cannot save; decimals and zero do save', async ({page}) => {
  const state = await setup(page);
  await edit(page);
  for (const value of ['-1','1e5']) {
    await page.getByLabel('Calories',{exact:true}).fill(value);
    await page.getByRole('button',{name:'Save meal'}).click();
    await expect(page.getByRole('dialog',{name:'Meal editor'}).getByRole('alert')).toContainText('0 or more');
    expect(state.requests.filter(r => r.method === 'POST' && r.path === '/api/meals')).toHaveLength(0);
  }
  await page.getByLabel('Calories',{exact:true}).fill('123.75');
  await page.getByLabel('Protein (g)',{exact:true}).fill('0');
  await page.getByRole('button',{name:'Save meal'}).click();
  await expect.poll(() => state.rows.find(r => r.meal_id === 1).calories).toBe(123.75);
});

test('direct USDA search: encoding, pagination, serving autofill and no backend calls until save', async ({page}) => {
  const state = await setup(page);
  await expect(page.locator('.logItemName')).toHaveCount(2);
  const baseline = state.requests.length;
  await foodSearch(page);
  await expect(page.getByRole('button',{name:/Rice & beans/})).toBeVisible();
  await page.getByRole('button',{name:'More results'}).click();
  await expect(page.getByRole('button',{name:/Second page food/})).toBeVisible();
  await page.getByRole('button',{name:'Previous results'}).click();
  await page.getByRole('button',{name:/Rice & beans/}).click();
  await expect(page.getByRole('dialog',{name:'Meal editor'})).toBeVisible();
  await page.getByLabel('Serving size',{exact:true}).selectOption('2');
  await expect(page.getByRole('dialog',{name:'Meal editor'})).toContainText('120');
  await page.getByRole('button',{name:'Edit details',exact:true}).click();
  await expect(page.getByLabel('Calories',{exact:true})).toHaveValue('120');
  await expect(page.getByLabel('Protein (g)',{exact:true})).toHaveValue('0');
  await expect(page.getByLabel('Carbs (g)',{exact:true})).toHaveValue('');
  expect(state.requests.length).toBe(baseline);
  expect(state.usdaRequests.map(r => r.page)).toEqual(['1','2']);
  expect(state.usdaRequests[0].query).toBe('rice & beans');
  await page.getByLabel('Calories',{exact:true}).fill('125');
  await page.getByRole('button',{name:'Add to Breakfast',exact:true}).click();
  await expect.poll(() => state.rows.some(r => r.food_name === 'Rice & beans' && r.calories === 125)).toBeTruthy();
});

test('no search results and manual entry without searching', async ({page}) => {
  const state = await setup(page);
  await foodSearch(page,'no results');
  await expect(page.getByRole('status')).toContainText('No foods matched');
  await expect(page.locator('.logSearchDropdown')).toHaveCount(0);
  await page.getByRole('button',{name:'Enter manually'}).click();
  await page.getByLabel('Food',{exact:true}).fill('Manual food');
  await page.getByLabel('Calories',{exact:true}).fill('0');
  await page.getByRole('button',{name:'Save meal'}).click();
  await expect.poll(() => state.rows.some(r => r.food_name === 'Manual food' && r.calories === 0)).toBeTruthy();
  await page.getByRole('button',{name:'Log lunch',exact:true}).click();
  await page.getByRole('button',{name:'Enter manually'}).click();
  expect(state.usdaRequests).toHaveLength(1);
  await expect(page.getByRole('dialog',{name:'Meal editor'})).toBeVisible();
});

test('delete uses ID route, no request body, removes only selected meal', async ({page}) => {
  const state = await setup(page);
  await page.getByRole('button',{name:'Remove Early breakfast'}).click();
  await expect(page.locator('.logItemName').filter({hasText:'Early breakfast'})).toHaveCount(0);
  expect(state.requests.find(r => r.method === 'DELETE')).toMatchObject({path:'/api/meals/1',body:null});
  expect(state.rows.map(r => r.meal_id).sort()).toEqual([2,3]);
});

for (const operation of ['GET','POST','DELETE','goals']) {
  test(`401 from ${operation} returns normal-login user to login`, async ({page}) => {
    const state = await setup(page);
    if (operation === 'GET') {
      state.expired = 'GET';
      await page.getByRole('button',{name:'← Prev'}).click();
    } else if (operation === 'POST') {
      await edit(page);
      state.expired = 'POST';
      await page.getByRole('button',{name:'Save meal'}).click();
    } else if (operation === 'DELETE') {
      state.expired = 'DELETE';
      await page.getByRole('button',{name:'Remove Early breakfast'}).click();
    } else {
      state.expired = 'POST';
      await page.getByRole('button',{name:'Edit Goals',exact:true}).click();
      await page.getByRole('button',{name:'Save Goals',exact:true}).click();
    }
    await expect(page.getByRole('button',{name:'Log In',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Log breakfast',exact:true})).toHaveCount(0);
  });
}


test('new meals use the current time and keep the chosen section after reload', async ({page}) => {
  const state = await setup(page);
  await page.clock.setFixedTime(new Date(`${TODAY}T19:37:00Z`));
  await page.getByRole('button',{name:'Log breakfast',exact:true}).click();
  await page.getByRole('button',{name:'Enter manually'}).click();
  await expect(page.getByLabel('Time',{exact:true})).toHaveValue('14:37:00');
  await page.getByLabel('Food',{exact:true}).fill('Late breakfast');
  await page.getByRole('button',{name:'Save meal'}).click();
  await expect.poll(() => state.rows.find(r => r.food_name === 'Late breakfast')?.consumed_at).toBe(`${TODAY}T19:37:00.000Z`);
  expect(state.rows.find(r => r.food_name === 'Late breakfast').meal_type).toBe('breakfast');
  await expect(page.getByRole('list',{name:'Breakfast meals'})).toContainText('Late breakfast');
  await page.getByRole('button',{name:'← Prev'}).click();
  await page.getByRole('button',{name:'Today',exact:true}).click();
  await expect(page.getByRole('list',{name:'Breakfast meals'})).toContainText('Late breakfast');
  await page.clock.setFixedTime(new Date(`${TODAY}T20:09:00Z`));
  await page.getByRole('button',{name:'Log lunch',exact:true}).click();
  await page.getByLabel('Search food',{exact:true}).fill('rice');
  await page.getByRole('button',{name:/Rice & beans/}).click();
  await page.getByRole('button',{name:'Add to Lunch',exact:true}).click();
  await expect.poll(() => state.rows.find(r => r.food_name === 'Rice & beans')?.consumed_at).toBe(`${TODAY}T20:09:00.000Z`);
  await expect(page.getByRole('list',{name:'Lunch meals'})).toContainText('Rice & beans');
});
