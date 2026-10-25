export const NUTRIENT_FIELDS = [
  { key: "calories", label: "Calories", unit: "" },
  { key: "protein", label: "Protein", unit: "g" },
  { key: "carbs", label: "Carbs", unit: "g" },
  { key: "cholesterol", label: "Cholesterol", unit: "mg" },
  { key: "trans_fats", label: "Trans Fats", unit: "g" },
  { key: "saturated_fats", label: "Saturated Fats", unit: "g" },
  { key: "total_fats", label: "Total Fats", unit: "g" },
];

const NUMBER_PATTERN = /^(\d+\.?\d*|\.\d+)$/;

export function getLocalDate(when = new Date()) {
  const year = when.getFullYear();
  const month = String(when.getMonth() + 1).padStart(2, "0");
  const day = String(when.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

export function makeZeroTotals() {
  const totals = {};

  for (const { key } of NUTRIENT_FIELDS) {
    totals[key] = 0;
  }

  return totals;
}

export function pickCurrentGoals(goalRows, today = getLocalDate()) {
  const current = goalRows
    .filter((row) => String(row.effective_date) <= today)
    .sort((a, b) =>
      String(a.effective_date).localeCompare(String(b.effective_date))
    )
    .pop();

  if (!current) {
    return { goals: {}, effectiveDate: null };
  }

  // MIN/MAX (turned off for now):
  // const typeRow = typeRows.find(
  //   (row) => String(row.effective_date) === String(current.effective_date)
  // );
  // const types = typeRow ? typeRow.types : {};

  const goals = {};

  for (const { key } of NUTRIENT_FIELDS) {
    const value = current[key];

    if (typeof value === "number" && value >= 0) {
      goals[key] = { target: value };
      // MIN/MAX: goals[key] = { target: value, type: types[key] || "max" };
    }
  }

  return { goals, effectiveDate: String(current.effective_date) };
}

export function makeGoalRequests(goals, day = getLocalDate()) {
  const values = { effective_date: day };
  // MIN/MAX: const types = {};

  for (const { key } of NUTRIENT_FIELDS) {
    if (goals[key]) {
      values[key] = goals[key].target;
      // MIN/MAX: types[key] = goals[key].type;
    }
  }

  return {
    values,
    // MIN/MAX: types: { effective_date: day, types },
  };
}

export function makeDraftGoals(goals) {
  const draft = {};

  for (const { key } of NUTRIENT_FIELDS) {
    const goal = goals[key];

    draft[key] = {
      tracked: Boolean(goal),
      target: goal ? String(goal.target) : "",
      // MIN/MAX: type: goal ? goal.type : "max",
    };
  }

  return draft;
}

export function parseGoalDraft(draft) {
  const goals = {};

  for (const { key, label } of NUTRIENT_FIELDS) {
    const choice = draft[key];

    if (!choice || !choice.tracked) {
      continue;
    }

    const text = String(choice.target).trim();

    if (!NUMBER_PATTERN.test(text)) {
      return { error: `${label} goal must be a number that is 0 or more.` };
    }

    // MIN/MAX:
    // if (choice.type !== "min" && choice.type !== "max") {
    //   return { error: `${label} goal must be a min or a max.` };
    // }

    goals[key] = { target: Number(text) };
    // MIN/MAX: goals[key] = { target: Number(text), type: choice.type };
  }

  return { goals };
}
