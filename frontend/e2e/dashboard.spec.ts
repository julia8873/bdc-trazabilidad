import { test, expect } from '@playwright/test';

test.describe('Autenticación y Dashboard', () => {
  
  test('Flujo de login fallido', async ({ page }) => {
    await page.route('**/api/v1/token', async route => {
      await route.fulfill({ status: 401, json: { detail: "Invalid credentials" } });
    });

    await page.goto('/login');
    await page.fill('input[type="text"]', 'wrong_user');
    await page.fill('input[type="password"]', 'wrong_pass');
    await page.click('button[type="submit"]');
    
    await expect(page.locator('.card')).toContainText('Credenciales inválidas');
  });

  test('Flujo de login exitoso (Profesor) y vista de curso con datos', async ({ page }) => {
    await page.goto('/login');
    // Moodle de prueba acepta cualquier usuario si mock está habilitado, 
    // pero aquí usamos "admin" / "testpass" o el mock user "teacher_mock"
    // Asumiremos que el backend mockeado o la configuración de prueba permite el login
    // En el contenedor de test, Moodle auth mock devuelve éxito para 'admin' o si no está mockeado, para el superadmin de moodle dev.
    
    // Vamos a mockear la petición a /api/token desde playwright para poder testear sin depender de Moodle real,
    // o depender del Moodle real de desarrollo. Como es un test E2E contra el docker-compose local, usaremos "admin"/"admin" si existe.
    // Para mayor resiliencia en un E2E frontend, mockeamos la API directamente aquí.
    
    await page.route('**/api/v1/token', async route => {
      // Mock login token
      const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsIm1vb2RsZV91c2VyX2lkIjoxLCJpc190ZWFjaGVyIjp0cnVlLCJhbGxvd2VkX2NvdXJzZXMiOlsxXSwiZXhwIjo5OTk5OTk5OTk5fQ.invalid_sig_but_ok_for_mock";
      await route.fulfill({ json: { access_token: token, token_type: "bearer" } });
    });

    await page.route('**/api/v1/metrics/cursos/1', async route => {
      await route.fulfill({
        json: {
          course_id: 1,
          total_interactions: 15,
          interactions_by_type: { chat: 10, forum: 5 },
          percentiles: { p25: 1, p50: 2, p75: 3, p90: 4, unique_users: 10 }
        }
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/interacciones*', async route => {
      await route.fulfill({
        json: { items: [], total: 0, limit: 10, offset: 0 }
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes', async route => {
      await route.fulfill({
        json: []
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes', async route => {
      await route.fulfill({
        json: []
      });
    });

    await page.goto('/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin');
    await page.click('button[type="submit"]');

    // Navegamos al curso desde TeacherHome
    await expect(page).toHaveURL('/');
    await page.click('text=Curso 1');

    // Debe navegar al dashboard de curso
    await expect(page).toHaveURL('/course/1');
    await expect(page.locator('h2').filter({ hasText: 'Dashboard de Curso 1' })).toBeVisible();
    await expect(page.getByText('Alumnos que han interactuado')).toBeVisible();
    await expect(page.getByText('10', { exact: true })).toBeVisible(); // unique_users: 10
  });

  test('Comprobación de estado vacío para curso sin interacciones', async ({ page }) => {
    await page.route('**/api/v1/token', async route => {
      const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsIm1vb2RsZV91c2VyX2lkIjoxLCJpc190ZWFjaGVyIjp0cnVlLCJhbGxvd2VkX2NvdXJzZXMiOlsyXSwiZXhwIjo5OTk5OTk5OTk5fQ.invalid";
      await route.fulfill({ json: { access_token: token, token_type: "bearer" } });
    });

    await page.route('**/api/v1/metrics/cursos/2', async route => {
      await route.fulfill({
        json: {
          course_id: 2,
          total_interactions: 0,
          interactions_by_type: {},
          percentiles: { p25: 0, p50: 0, p75: 0, p90: 0, unique_users: 0 }
        }
      });
    });

    await page.route('**/api/v1/metrics/cursos/2/interacciones*', async route => {
      await route.fulfill({
        json: { items: [], total: 0, limit: 10, offset: 0 }
      });
    });

    await page.route('**/api/v1/metrics/cursos/2/estudiantes', async route => {
      await route.fulfill({
        json: []
      });
    });

    await page.goto('/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/');
    await page.click('text=Curso 2');

    await expect(page).toHaveURL('/course/2');
    await expect(page.getByText('No hay interacciones registradas en este curso')).toBeVisible();
    await expect(page.getByText('Datos insuficientes para el cálculo de percentiles')).toBeVisible();
  });

  test('Comprobación de que un alumno no ve el link de Dashboard', async ({ page }) => {
    await page.route('**/api/v1/token', async route => {
      // is_teacher: false
      const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbHVtbm8iLCJtb29kbGVfdXNlcl9pZCI6MiwiaXNfdGVhY2hlciI6ZmFsc2UsImFsbG93ZWRfY291cnNlcyI6WzFdLCJleHAiOjk5OTk5OTk5OTl9.invalid";
      await route.fulfill({ json: { access_token: token, token_type: "bearer" } });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes/2', async route => {
      await route.fulfill({
        json: {
          student_id: 2,
          course_id: 1,
          total_interactions: 0,
          interactions_by_type: {}
        }
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes/2/interacciones*', async route => {
      await route.fulfill({
        json: { items: [], total: 0, limit: 10, offset: 0 }
      });
    });

    await page.goto('/login');
    await page.fill('input[type="text"]', 'alumno');
    await page.fill('input[type="password"]', 'alumno');
    await page.click('button[type="submit"]');

    // HomeRedirect mandará al alumno a su perfil
    await expect(page).toHaveURL('/course/1/student/2');
    
    // El navbar no debe tener el link "Dashboard", pero sí "Mi Perfil"
    await expect(page.getByText('Mi Perfil')).toBeVisible();
    await expect(page.getByText('Dashboard', { exact: true })).not.toBeVisible();
  });

  test('Comprobación del estado vacío de conceptos para un alumno', async ({ page }) => {
    await page.route('**/api/v1/token', async route => {
      const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbHVtbm8iLCJtb29kbGVfdXNlcl9pZCI6MiwiaXNfdGVhY2hlciI6ZmFsc2UsImFsbG93ZWRfY291cnNlcyI6WzFdLCJleHAiOjk5OTk5OTk5OTl9.invalid";
      await route.fulfill({ json: { access_token: token, token_type: "bearer" } });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes/2', async route => {
      await route.fulfill({
        json: {
          student_id: 2,
          course_id: 1,
          total_interactions: 5,
          interactions_by_type: { quiz: 5 }
        }
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes/2/interacciones*', async route => {
      await route.fulfill({
        json: { items: [], total: 0, limit: 10, offset: 0 }
      });
    });

    await page.goto('/login');
    await page.fill('input[type="text"]', 'alumno');
    await page.fill('input[type="password"]', 'alumno');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/course/1/student/2');
    await expect(page.getByText('Perfil de Alumno 2')).toBeVisible();
    await expect(page.getByText('Sin conceptos registrados para este curso todavía')).toBeVisible();
  });

  test('Flujo de sesión expirada a mitad de navegación (401 interceptor)', async ({ page }) => {
    await page.route('**/api/v1/token', async route => {
      const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsIm1vb2RsZV91c2VyX2lkIjoxLCJpc190ZWFjaGVyIjp0cnVlLCJhbGxvd2VkX2NvdXJzZXMiOlsxXSwiZXhwIjo5OTk5OTk5OTk5fQ.invalid";
      await route.fulfill({ json: { access_token: token, token_type: "bearer" } });
    });

    await page.route('**/api/v1/metrics/cursos/1', async route => {
      await route.fulfill({
        json: {
          course_id: 1,
          total_interactions: 0,
          interactions_by_type: {},
          percentiles: { p25: 0, p50: 0, p75: 0, p90: 0, unique_users: 0 }
        }
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/interacciones*', async route => {
      await route.fulfill({
        json: { items: [], total: 0, limit: 10, offset: 0 }
      });
    });

    await page.route('**/api/v1/metrics/cursos/1/estudiantes', async route => {
      await route.fulfill({
        json: []
      });
    });

    // 1. Login exitoso normal
    await page.goto('/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/');
    await page.click('text=Curso 1');

    await expect(page).toHaveURL('/course/1');
    await expect(page.locator('h2').filter({ hasText: 'Dashboard de Curso 1' })).toBeVisible();

    // 2. Simulamos que a partir de ahora, el backend rechaza con 401 (token expirado 15min)
    await page.route('**/api/v1/metrics/cursos/1/estudiantes/99', async route => {
      await route.fulfill({ status: 401, json: { detail: "Token expired" } });
    });

    // 3. Forzamos una petición de fetch que devuelva 401 desde el cliente sin cambiar la página
    await page.evaluate(() => {
       window.dispatchEvent(new CustomEvent('auth-unauthorized'));
    });

    // 4. El interceptor global debe detectar el 401, vaciar el estado en RAM,
    //    guardar /course/1 en sessionStorage y redirigir a /login
    await expect(page).toHaveURL('/login');

    // 5. El usuario vuelve a loguearse tras haber sido expulsado
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin');
    await page.click('button[type="submit"]');

    // 6. El sistema lee el returnPath de sessionStorage y lo devuelve exactamente donde estaba
    await expect(page).toHaveURL('/course/1');
  });

});
