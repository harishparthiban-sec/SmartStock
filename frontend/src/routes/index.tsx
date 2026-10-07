import { Routes, Route } from 'react-router-dom';
import { AppShell } from '../layouts/AppShell';

import Overview from '../pages/Overview';
import ProductDetail from '../pages/ProductDetail';
import WhatIf from '../pages/WhatIf';
import ModelImpact from '../pages/ModelImpact';
import Overstock from '../pages/Overstock';
import DemandTimeMachine from '../pages/DemandTimeMachine';
import Copilot from '../pages/Copilot';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="products/:productId" element={<ProductDetail />} />
        <Route path="what-if" element={<WhatIf />} />
        <Route path="model-impact" element={<ModelImpact />} />
        <Route path="overstock" element={<Overstock />} />
        <Route path="time-machine" element={<DemandTimeMachine />} />
        <Route path="copilot" element={<Copilot />} />
      </Route>
    </Routes>
  );
}
