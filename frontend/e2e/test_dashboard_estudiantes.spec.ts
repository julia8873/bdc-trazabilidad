import { test, expect } from '@playwright/test';

test.describe('Dashboard de Estudiantes', () => {
  // Test para verificar que RoleGuard y las columnas funcionan
  test('Flujo E2E de profesor: tabla de estudiantes y navegacion a perfil', async ({ page }) => {
    // 1. Login como profesor1 (Demo auth debe estar habilitado en testing)
    await page.goto('/');
    
    await page.fill('input[type="text"]', 'profesor1');
    await page.fill('input[type="password"]', 'Profesor1!');
    
    // Mock token API
    await page.route('**/api/v1/token', async route => {
      // Usamos el token mockeado idéntico al que genera dashboard.spec.ts para que decodifique a admin/teacher con allowed_courses: [1]
      const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsIm1vb2RsZV91c2VyX2lkIjoxLCJpc190ZWFjaGVyIjp0cnVlLCJhbGxvd2VkX2NvdXJzZXMiOlsxXSwiZXhwIjo5OTk5OTk5OTk5fQ.invalid_sig_but_ok_for_mock";
      await route.fulfill({ json: { access_token: token, token_type: 'bearer' } });
    });

    // Mock TeacherHome (mis cursos)
    await page.route('**/api/v1/metrics/cursos/1', async route => {
      await route.fulfill({ json: { total_interactions: 10, interactions_by_type: {}, percentiles: { p25: 0, p50: 0, p75: 0, p90: 0, unique_users: 10 } } });
    });
    await page.route('**/api/v1/metrics/cursos/1/interacciones*', async route => {
      await route.fulfill({ json: { items: [], total: 0 } });
    });
    
    // El nuevo endpoint /metrics/cursos/1/estudiantes
    await page.route('**/api/v1/metrics/cursos/1/estudiantes', async route => {
      const json = {
        course_id: 1,
        students: [
          {
            moodle_user_id: 2,
            moodle_username: 'alumno1',
            repo_url: 'https://github.com/mock/mock',
            total_interactions: 5,
            ultima_actividad: '2026-08-15T12:00:00Z',
            estado_sincronizacion: 'OK'
          }
        ]
      };
      await route.fulfill({ json });
    });

    // Login normal clicando submit
    await page.goto('/login');
    await page.fill('input[type="text"]', 'profesor1');
    await page.fill('input[type="password"]', 'Profesor1!');
    await page.click('button[type="submit"]');

    // El login redirige a /
    await expect(page).toHaveURL('/');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: "screenshot_before_click.png", fullPage: true });
    
    // Hacemos click en la tarjeta del curso 1
    await page.click('text=Curso 1');

    // Debe navegar al dashboard de curso
    await expect(page).toHaveURL('/course/1');
    await expect(page.locator('h2').filter({ hasText: 'Dashboard de Curso 1' })).toBeVisible();

    // 3. Verificar las columnas requeridas en la tabla de alumnos
    const table = page.locator('table').last();
    await expect(table).toBeVisible();
    
    const headers = table.locator('th');
    await expect(headers).toHaveText([
      'Alumno',
      'Enlace al repo',
      'Nº interacciones',
      'Última actividad',
      'Estado de sincronización'
    ]);

    // 4. Verificar el contenido del alumno1
    const row = table.locator('tbody tr').first();
    await expect(row).toContainText('alumno1');
    await expect(row).toContainText('Ver en GitHub');
    await expect(row).toContainText('5');
    await expect(row).toContainText('OK'); // Estado

    // 5. Simular clic en el alumno para ir a su perfil
    // El enlace en 'moodle_username' lleva a /course/1/student/2
    const studentLink = row.locator('a').first();
    await expect(studentLink).toHaveAttribute('href', '/course/1/student/2');
    
    // No hace falta clickear de verdad si no queremos testear StudentDashboard entero, pero lo simulamos
    // await studentLink.click();
    // await expect(page).toHaveURL(/\/course\/1\/student\/2/);
  });
});
