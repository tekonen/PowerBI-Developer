# Semantic Model: HR Analytics

## Table: Employee
| Column | Type | Description |
|--------|------|-------------|
| EmployeeID | Integer | Unique employee identifier |
| Name | String | Full name |
| Department | String | Department name |
| JobTitle | String | Job title |
| Gender | String | Gender |
| StartDate | Date | Employment start date |
| EndDate | Date | Employment end date (null if active) |
| ManagerID | Integer | Manager employee ID |
| Location | String | Office location |
| Salary | Decimal | Annual salary |

## Table: Date
| Column | Type | Description |
|--------|------|-------------|
| Date | Date | Calendar date |
| Year | Integer | Calendar year |
| Quarter | String | Q1-Q4 |
| MonthYear | String | MMM YYYY format |
| MonthNum | Integer | Month number 1-12 |
| IsCurrentMonth | Boolean | True if current month |

### Measures in Date
- **Today**: `TODAY()`

## Table: HR Measures
### Measures in HR Measures
- **Headcount**: `COUNTROWS(FILTER(Employee, Employee[StartDate] <= MAX(Date[Date]) && (ISBLANK(Employee[EndDate]) || Employee[EndDate] > MAX(Date[Date]))))`
  Active employee count as of the selected date
- **Attrition Rate**: `DIVIDE([Leavers], [Avg Headcount], 0)`
  Rolling attrition rate
- **Leavers**: `COUNTROWS(FILTER(Employee, Employee[EndDate] >= MIN(Date[Date]) && Employee[EndDate] <= MAX(Date[Date])))`
  Count of employees who left in the period
- **Avg Headcount**: `DIVIDE([Headcount] + [Prior Period Headcount], 2)`
  Average headcount over the period
- **Prior Period Headcount**: `CALCULATE([Headcount], DATEADD(Date[Date], -1, MONTH))`
  Headcount from previous period
- **New Hires**: `COUNTROWS(FILTER(Employee, Employee[StartDate] >= MIN(Date[Date]) && Employee[StartDate] <= MAX(Date[Date])))`
  Count of new hires in the period
- **Gender Ratio Female**: `DIVIDE(CALCULATE([Headcount], Employee[Gender] = "Female"), [Headcount], 0)`
  Percentage of female employees
- **Avg Tenure (Years)**: `AVERAGEX(FILTER(Employee, ISBLANK(Employee[EndDate])), DATEDIFF(Employee[StartDate], TODAY(), YEAR))`
  Average tenure of active employees

## Relationships
| From | To | Cardinality | Filter |
|------|-----|-------------|--------|
| Employee[StartDate] | Date[Date] | ManyToOne | Single |
