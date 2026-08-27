import { test, expect } from '@playwright/test';

test.describe('Student Profile - Filtros de Línea Temporal', () => {
  test.beforeEach(async ({ page }) => {
    // Mock Auth (Refresh endpoint)
    await page.route('**/api/refresh', async route => {
      // Create a valid base64 payload for jwtDecode
      const payload = btoa(JSON.stringify({
        sub: '1',
        moodle_user_id: 1,
        is_teacher: true,
        allowed_courses: [3],
        exp: 9999999999
      }));
      const fakeJwt = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: fakeJwt,
          token_type: 'bearer'
        })
      });
    });

    // Mock the API endpoints for Student Profile
    await page.route('**/v1/metrics/cursos/3/estudiantes/99', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          student_id: 99,
          course_id: 3,
          total_interactions: 5,
          interactions_by_type: { duda_teorica: 2, duda_practica: 2, fuera_de_ambito: 1 }
        })
      });
    });

    await page.route('**/v1/metrics/cursos/3/estudiantes/99/conceptos', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          conceptos: { vectores: 2, matrices: 2 }
        })
      });
    });

    await page.route('**/v1/metrics/cursos/3/estudiantes/99/interacciones*', async route => {
      const url = new URL(route.request().url());
      const tipo = url.searchParams.get('tipo');
      const concepto = url.searchParams.get('concepto');
      
      let items = [
        { id: '1', timestamp: '2026-08-01T10:00:00Z', tipo_interaccion: 'duda_teorica', concepto: ['vectores'] },
        { id: '2', timestamp: '2026-08-02T10:00:00Z', tipo_interaccion: 'duda_practica', concepto: ['matrices'] },
        { id: '3', timestamp: '2026-08-03T10:00:00Z', tipo_interaccion: 'fuera_de_ambito', concepto: [] }
      ];

      if (tipo) {
        items = items.filter(i => i.tipo_interaccion === tipo);
      }
      if (concepto) {
        items = items.filter(i => i.concepto.includes(concepto));
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items,
          total: items.length,
          limit: 50,
          offset: 0
        })
      });
    });
  });

  test('Filtra correctamente por tipo de interaccion y concepto', async ({ page }) => {
    // Navigate to student profile
    await page.goto('/course/3/student/99');

    // Comprobar que carga inicialmente todas las interacciones
    await expect(page.locator('div').filter({ hasText: /^duda_teorica$/ }).first()).toBeVisible();
    await expect(page.locator('div').filter({ hasText: /^duda_practica$/ }).first()).toBeVisible();
    await expect(page.locator('div').filter({ hasText: /^fuera_de_ambito$/ }).first()).toBeVisible();

    // Seleccionar filtro por tipo "duda_teorica"
    await page.locator('select').nth(0).selectOption('duda_teorica');

    // Verificamos que duda_teorica sigue visible y duda_practica no
    await expect(page.locator('div').filter({ hasText: /^duda_teorica$/ }).first()).toBeVisible();
    await expect(page.locator('div').filter({ hasText: /^duda_practica$/ }).first()).toBeHidden();

    // Volver a todos los tipos y filtrar por concepto "matrices"
    await page.locator('select').nth(0).selectOption('');
    await page.locator('select').nth(1).selectOption('matrices');

    // Verificamos que ahora solo está duda_practica
    await expect(page.locator('div').filter({ hasText: /^duda_teorica$/ }).first()).toBeHidden();
    await expect(page.locator('div').filter({ hasText: /^duda_practica$/ }).first()).toBeVisible();
  });
});
