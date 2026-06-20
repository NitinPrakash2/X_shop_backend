@echo off
REM Test X Shop APIs - Check for 200 OK responses

setlocal enabledelayedexpansion

set BASE_URL=http://localhost:8000/client/api/i/ona/xshop
set EMAIL=test@example.com
set PASSWORD=Test@123456

echo.
echo ====================================================
echo X SHOP API TESTING - Terminal Output
echo ====================================================
echo.

REM Test 1: Register
echo [1/5] Testing REGISTER endpoint...
curl -X POST %BASE_URL% ^
  -H "Content-Type: application/json" ^
  -d "{\"action\":\"register\",\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"full_name\":\"Test User\"}" ^
  -w "\nHTTP Status: %%{http_code}\n" ^
  -s

echo.
echo [2/5] Testing LOGIN endpoint...
curl -X POST %BASE_URL% ^
  -H "Content-Type: application/json" ^
  -d "{\"action\":\"login\",\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\"}" ^
  -w "\nHTTP Status: %%{http_code}\n" ^
  -s

echo.
echo [3/5] Testing GET_PRODUCTS endpoint (requires Bearer token)...
REM Note: Replace TOKEN with actual JWT from login response
set TOKEN=your_jwt_token_here
curl -X POST %BASE_URL% ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer %TOKEN%" ^
  -d "{\"action\":\"get_products\",\"page\":1,\"limit\":20}" ^
  -w "\nHTTP Status: %%{http_code}\n" ^
  -s

echo.
echo [4/5] Testing X_OAUTH_INIT endpoint (requires Bearer token)...
curl -X POST %BASE_URL% ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer %TOKEN%" ^
  -d "{\"action\":\"x_oauth_init\"}" ^
  -w "\nHTTP Status: %%{http_code}\n" ^
  -s

echo.
echo [5/5] Testing GET_DASHBOARD endpoint (requires Bearer token)...
curl -X POST %BASE_URL% ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer %TOKEN%" ^
  -d "{\"action\":\"get_dashboard\"}" ^
  -w "\nHTTP Status: %%{http_code}\n" ^
  -s

echo.
echo ====================================================
echo Testing Complete
echo ====================================================
echo.
echo NOTE: 
echo - 200 OK = Success
echo - 201 Created = Resource created
echo - 400 Bad Request = Invalid input
echo - 401 Unauthorized = No/Invalid token
echo - 404 Not Found = Action not found
echo - 422 Unprocessable = Validation error
echo.

endlocal
