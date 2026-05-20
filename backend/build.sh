#!/bin/bash
cd ../frontend
npm install
npm run build
cp -r dist ../backend/static
cd ../backend	