import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./FoodLog.css";
import { getMealsByDate, logMeal, removeMeal, UnauthorizedError } from "../api/meals";
import { searchFoodPage, foodToMeal } from "../api/foodDataCentral";
import { getLocalDate, NUTRIENT_FIELDS, makeEmptyMealDraft, parseMealDraft } from "../utils/nutrition";

const MEAL_LABELS = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner", snacks: "Snacks" };
function mealSection(meal) {
  if (Object.hasOwn(MEAL_LABELS, meal.meal_type)) return meal.meal_type;
  const hour = new Date(meal.consumed_at).getHours();
  return hour < 11 ? "breakfast" : hour < 15 ? "lunch" : hour < 21 ? "dinner" : "snacks";
}

function shiftDate(value, delta) {
  const day = new Date(`${value}T12:00:00`);
  day.setDate(day.getDate() + delta);
  return getLocalDate(day);
}

function draftFromMeal(meal, date) {
  const when = meal?.consumed_at ? new Date(meal.consumed_at) : new Date();
  const draft = { ...makeEmptyMealDraft(), food_name: meal?.food_name || "",
    date: meal?.consumed_at ? getLocalDate(when) : date, time: when.toTimeString().slice(0, 8) };
  for (const { key } of NUTRIENT_FIELDS) {
    if (meal?.[key] != null && meal[key] >= 0) draft[key] = String(meal[key]);
  }
  return draft;
}

export default function FoodLog({ userId, isDemo = false, onMealsChange, onUnauthorized, renderSummary }) {
  const [selectedDate, setSelectedDate] = useState(getLocalDate);
  const [savedMeals, setSavedMeals] = useState([]);
  const [demoMeals, setDemoMeals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [editor, setEditor] = useState(null);
  const [draft, setDraft] = useState(null);
  const searchVersion = useRef(0);
  const [expandedSection, setExpandedSection] = useState(null);

  const [query, setQuery] = useState("");
  const [amount, setAmount] = useState("100");
  const [unit, setUnit] = useState("grams");
  const [results, setResults] = useState([]);
  const [searchStatus, setSearchStatus] = useState("");
  const [resultPage, setResultPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [lastQuery, setLastQuery] = useState("");
  const [sourceFood, setSourceFood] = useState(null);
  const [targetSection, setTargetSection] = useState(null);
  const [editingDetails, setEditingDetails] = useState(false);

  useEffect(() => {
    if (isDemo || !userId) return;
    let active = true;
    getMealsByDate(selectedDate).then((rows) => {
      if (active) { setSavedMeals(rows); setLoading(false); }
    }).catch((err) => {
      if (!active) return;
      if (err instanceof UnauthorizedError) onUnauthorized?.();
      else setError(err.message);
      setLoading(false);
    });
    return () => { active = false; };
  }, [selectedDate, isDemo, userId, revision, onUnauthorized]);

  const meals = useMemo(() => (isDemo ? demoMeals : savedMeals)
    .filter((meal) => getLocalDate(new Date(meal.consumed_at)) === selectedDate)
    .sort((a, b) => new Date(a.consumed_at) - new Date(b.consumed_at) || String(a.meal_id).localeCompare(String(b.meal_id))),
  [demoMeals, savedMeals, isDemo, selectedDate]);
  useEffect(() => { onMealsChange?.(meals); }, [meals, onMealsChange]);
  const selected = meals.find((meal) => meal.meal_id === selectedId);

  function changeDay(date) {
    if (saving || date > getLocalDate()) return;
    searchVersion.current++;
    setSelectedDate(date); setSavedMeals([]); setSelectedId(null);
    setEditor(null); setExpandedSection(null); setError(""); setLoading(!isDemo);
  }
  function openEditor(meal = null) {
    searchVersion.current++;
    setSourceFood(null); setEditingDetails(true); setTargetSection(expandedSection);
    const next = draftFromMeal(meal, selectedDate);
    setDraft(next);
    setEditor(meal ? { meal_id: meal.meal_id, meal_type: mealSection(meal) } : { meal_type: expandedSection });
    setExpandedSection(null); setError("");
  }
  const search = useCallback(async (term, page = 1) => {
    const version = ++searchVersion.current;
    setResults([]); setSearchStatus("Searching…");
    try {
      const { foods, totalPages: pages } = await searchFoodPage(term, page);
      if (version !== searchVersion.current) return;
      setResults(foods); setResultPage(page); setTotalPages(pages); setLastQuery(term);
      setSearchStatus(foods.length ? "" : "No foods matched your search.");
    } catch (err) { if (version === searchVersion.current) setSearchStatus(err.message); }
  }, []);
  useEffect(() => {
    if (!expandedSection || editor || query.trim().length < 2) return;
    const timer = setTimeout(() => search(query.trim()), 600);
    return () => clearTimeout(timer);
  }, [query, expandedSection, editor, search]);
  useEffect(() => () => { searchVersion.current++; }, []);

  function chooseFood(food) {
    const hasServingWeight = food.servingSize > 0 && ["g", "grm", "oz", "onz"].includes(String(food.servingSizeUnit).toLowerCase());
    const nextAmount = hasServingWeight ? "1" : "100";
    const nextUnit = hasServingWeight ? "servings" : "grams";
    const meal = foodToMeal(food, nextAmount, nextUnit);
    const next = draftFromMeal(meal, selectedDate);
    searchVersion.current++;
    setSourceFood(food); setTargetSection(expandedSection); setEditingDetails(false);
    setAmount(nextAmount); setUnit(nextUnit);
    setSelectedId(null); setDraft(next); setEditor({ meal_type: expandedSection }); setError("");
  }
  function changeServing(multiplier) {
    const quantity = Number(multiplier) * (unit === "servings" ? 1 : 100);
    const meal = foodToMeal(sourceFood, quantity, unit);
    setAmount(String(quantity));
    setDraft((previous) => {
      const next = { ...previous };
      for (const { key } of NUTRIENT_FIELDS) next[key] = meal[key] == null ? "" : String(meal[key]);
      return next;
    });
  }
  async function save(event) {
    event.preventDefault();
    const parsed = parseMealDraft(draft);
    if (parsed.error) { setError(parsed.error); return; }
    const when = new Date(`${draft.date}T${draft.time}`);
    if (!draft.date || !draft.time || Number.isNaN(when.getTime())) {
      setError("Enter a valid date and time."); return;
    }
    const body = { ...parsed.meal, ...editor, consumed_at: when.toISOString() };
    setSaving(true); setError("");
    try {
      if (isDemo) {
        const meal = { ...body, meal_id: editor.meal_id ?? `demo-${Date.now()}` };
        setDemoMeals((rows) => [...rows.filter((row) => row.meal_id !== meal.meal_id), meal]);
      } else {
        await logMeal(body); setRevision((value) => value + 1);
      }
      setEditor(null); setDraft(null); setSourceFood(null); setExpandedSection(null); setQuery(""); setResults([]);
    } catch (err) {
      if (err instanceof UnauthorizedError) onUnauthorized?.();
      else setError(err.message);
    } finally { setSaving(false); }
  }
  async function deleteSelected(meal = selected) {
    if (!meal) return;
    setSaving(true); setError("");
    try {
      if (isDemo) setDemoMeals((rows) => rows.filter((row) => row.meal_id !== meal.meal_id));
      else { await removeMeal(meal); setSavedMeals((rows) => rows.filter((row) => row.meal_id !== meal.meal_id)); }
      setSelectedId(null);
    } catch (err) {
      if (err instanceof UnauthorizedError) onUnauthorized?.();
      else setError(err.message);
    } finally { setSaving(false); }
  }
  const setField = (key, value) => setDraft((previous) => ({ ...previous, [key]: value }));

  function toggleSection(key) {
    searchVersion.current++;
    setExpandedSection((previous) => previous === key ? null : key);
    setQuery(""); setResults([]); setTotalPages(0); setSearchStatus(""); setError("");
  }
  async function resetLog() {
    if (!meals.length || !window.confirm("Clear all meals for this day?")) return;
    setSaving(true); setError("");
    try {
      if (isDemo) setDemoMeals((rows) => rows.filter((row) => getLocalDate(new Date(row.consumed_at)) !== selectedDate));
      else {
        for (const meal of meals) {
          await removeMeal(meal);
          setSavedMeals((rows) => rows.filter((row) => row.meal_id !== meal.meal_id));
        }
      }
      setSelectedId(null);
    } catch (err) {
      if (err instanceof UnauthorizedError) onUnauthorized?.();
      else setError(err.message);
    } finally { setSaving(false); }
  }

  return <section className="foodLog logPage" aria-label="Food log">
    <div className="logContent">
      <div className="logDateBar logDateBarTop">
        <button className="logDateBtn" disabled={saving} onClick={() => changeDay(shiftDate(selectedDate, -1))}>← Prev</button>
        <h2 className="logDateTitle">{selectedDate === getLocalDate() ? "Today" : new Date(`${selectedDate}T12:00:00`).toLocaleDateString("en-US", { weekday: "long" })}<small>{new Date(`${selectedDate}T12:00:00`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</small></h2>
        <div className="logDateActions">
          {selectedDate !== getLocalDate() && <button className="logTodayBtn" disabled={saving} onClick={() => changeDay(getLocalDate())}>Today</button>}
          <button className="logDateBtn" disabled={saving || selectedDate >= getLocalDate()} onClick={() => changeDay(shiftDate(selectedDate, 1))}>Next →</button>
        </div>
      </div>
      {renderSummary && <div className="logSummary">{renderSummary(meals)}</div>}
      <div className="logResetRow"><button className="logResetBtn" disabled={saving || !meals.length} onClick={resetLog}>Reset Log</button></div>
      {error && !editor && <p role="alert" className="logError">{error}</p>}
      {loading && <p role="status">Loading meals…</p>}
      <div className="logCard">
        {Object.entries(MEAL_LABELS).map(([key, label]) => {
          const items = meals.filter((meal) => mealSection(meal) === key);
          const expanded = expandedSection === key;
          return <section className="logSection" key={key}>
            <h2 className="logSectionTitle">{label}</h2>
            <div className="logAddRow">
              <button className="logAddBtn" disabled={saving} aria-label={`Log ${label.toLowerCase()}`} aria-expanded={expanded} onClick={() => toggleSection(key)}>+</button>
              <button className="logAddPrompt" disabled={saving} onClick={() => toggleSection(key)}>Log your {label.toLowerCase()} here</button>
            </div>
            {expanded && <div className="logExpand open">
              <div className="logSearchWrap"><input className="logInput" aria-label="Search food" placeholder="Search food..." value={query} onChange={(e) => { searchVersion.current++; setQuery(e.target.value); setResults([]); setSearchStatus(""); setTotalPages(0); }} autoFocus /></div>
              {searchStatus && <p role="status" className="logSearchLoading">{searchStatus}</p>}
              {results.length > 0 && <ul className="logSearchDropdown">{results.map((food) => <li key={food.fdcId}><button className="logSearchDropdownItem" onClick={() => chooseFood(food)}><span>{food.description}<small>{food.brandOwner}</small></span><span className="logSearchDropdownCals">{food.nutrients.calories == null ? "" : `${Math.round(food.nutrients.calories)} cal`}</span></button></li>)}</ul>}
              {totalPages > 1 && <div className="logInputRow" aria-label="Food result pages"><button className="flButton" disabled={resultPage <= 1 || searchStatus === "Searching…"} onClick={() => search(lastQuery, resultPage - 1)}>Previous results</button><span>Page {resultPage} of {totalPages}</span><button className="flButton" disabled={resultPage >= totalPages || searchStatus === "Searching…"} onClick={() => search(lastQuery, resultPage + 1)}>More results</button></div>}
              <button type="button" className="logManualLink" onClick={() => openEditor()}>Enter manually</button>
            </div>}
            {items.length ? <ul className="logItemList" aria-label={`${label} meals`}>{items.map((meal) => <li key={meal.meal_id} className="logItem logItemAnim">
              <button className="logItemName" onClick={() => { setSelectedId(meal.meal_id); setError(""); }}><span>{meal.food_name}{meal.calories != null && meal.calories >= 0 && <span className="logItemMeta"> · {Math.round(meal.calories)} cal</span>}</span><time dateTime={meal.consumed_at}>{new Date(meal.consumed_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</time></button>
              <button className="logItemRemove" disabled={saving} aria-label={`Remove ${meal.food_name}`} onClick={() => deleteSelected(meal)}>×</button>
            </li>)}</ul> : <div className="logEmptyState">{key === "breakfast" && selectedDate === getLocalDate() ? <><strong>Nothing logged yet.</strong> Start with your first meal of the day here.</> : "No items logged yet."}</div>}
          </section>;
        })}
      </div>
      {selected && !editor && <div className="logModalOverlay" role="dialog" aria-modal="true" aria-label="Meal details"><div className="logModal">
        <h3 className="logModalTitle">{selected.food_name}</h3>{error && <p role="alert" className="logError">{error}</p>}<p>{new Date(selected.consumed_at).toLocaleString("en-US", { month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })}</p>
        <div className="logModalNutrients">{NUTRIENT_FIELDS.filter(({ key }) => selected[key] != null && selected[key] >= 0).map(({ key, label, unit }) => <div key={key} className="logModalNutrientRow"><span>{label}</span><strong>{selected[key]}{unit}</strong></div>)}</div>
        <div className="logModalActions"><button className="logModalCancel" onClick={() => setSelectedId(null)}>Close</button><button className="logModalCancel" disabled={saving} onClick={() => deleteSelected()}>Delete</button><button className="logModalAdd" onClick={() => openEditor(selected)}>Edit</button></div>
      </div></div>}
    {editor && <div className="logModalOverlay" role="dialog" aria-modal="true" aria-label="Meal editor"><form className="foodLogForm logModal" onSubmit={save} noValidate>
      {error && <p role="alert" className="logError">{error}</p>}
      <h3 className="logModalTitle">{sourceFood ? sourceFood.description : editor.meal_id ? "Edit meal" : "New meal"}</h3>
      {sourceFood && !editingDetails && <>
        <div className="logModalNutrients">{NUTRIENT_FIELDS.filter(({ key }) => draft[key] !== "").map(({ key, label, unit: nutrientUnit }) => <div key={key} className="logModalNutrientRow"><span>{label === "Total Fats" ? "Fat" : label}</span><span>{draft[key]}{nutrientUnit}</span></div>)}</div>
        <label className="logModalServingLabel">Serving size
          <select aria-label="Serving size" className="logModalServingSelect" value={Number(amount) / (unit === "servings" ? 1 : 100)} onChange={(e) => changeServing(e.target.value)}>
            {[0.25, 0.5, 1, 1.5, 2, 2.5, 3].map((value) => <option key={value} value={value}>{value}{value === 1 ? " (default)" : "×"} — {unit === "servings" ? `${Number((sourceFood.servingSize * value).toFixed(2))} ${sourceFood.servingSizeUnit}` : `${value * 100} g`}</option>)}
          </select>
        </label>
        <button type="button" className="logManualLink" onClick={() => setEditingDetails(true)}>Edit details</button>
      </>}
      {(!sourceFood || editingDetails) && <>
        <label>Food<input maxLength={200} value={draft.food_name} disabled={saving} onChange={(e) => setField("food_name", e.target.value)} /></label>
        <div className="foodLogEditDateTime"><label>Date<input type="date" value={draft.date} disabled={saving} onChange={(e) => setField("date", e.target.value)} /></label><label>Time<input type="time" step="1" value={draft.time} disabled={saving} onChange={(e) => setField("time", e.target.value)} /></label></div>
        <p className="foodLogHint">Leave a nutrient blank to stop tracking it. Zero is a tracked value.</p>
        <div className="foodLogGrid">{NUTRIENT_FIELDS.map(({ key, label, unit: nutrientUnit }) => <label key={key}>{label}{nutrientUnit && ` (${nutrientUnit})`}<input type="number" min="0" step="any" placeholder="Untracked" value={draft[key]} disabled={saving} onChange={(e) => setField(key, e.target.value)} /></label>)}</div>
      </>}
      <div className="logModalActions"><button type="button" className="logModalCancel" disabled={saving} onClick={() => { setEditor(null); setDraft(null); setSourceFood(null); setError(""); }}>Cancel</button><button className="logModalAdd" disabled={saving}>{saving ? "Saving…" : sourceFood ? `Add to ${MEAL_LABELS[targetSection]}` : "Save meal"}</button></div>
    </form></div>}
    </div>
  </section>;
}
