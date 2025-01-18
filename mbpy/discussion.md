

Phases like `unpackPhase`, `buildPhase`, and `installPhase` can resemble **recipes** at first glance, especially compared to systems like **Conan** or other imperative tools. However, the key difference lies in how **declarative** systems like Nix handle these phases **implicitly and compositionally**, rather than requiring imperative scripting.

Here’s why **Nix derivations** differ fundamentally from traditional recipes:

---

### **1. Declarative Nature of Nix**
In Nix, you don't specify *how* to execute every step (imperative scripting). Instead, you declare:
- The desired inputs (`src`, `buildInputs`, etc.).
- The environment (`stdenv`, `nativeBuildInputs`).
- The desired output.

Nix’s **phases** are defaults inherited from `stdenv` (standard environment) and reused across derivations. You can override or extend these phases declaratively if needed, but the system works out the steps automatically based on inputs and outputs.

#### **Example: A Nix Derivation**
```nix
{ stdenv, fetchurl, cmake }:

stdenv.mkDerivation {
  name = "my-project";
  version = "1.0.0";

  src = fetchurl {
    url = "https://example.com/my-project-1.0.0.tar.gz";
    sha256 = "0xyz..."; # Integrity check
  };

  buildInputs = [ cmake ];

  # Only override if necessary
  configurePhase = ''
    cmake -DCMAKE_BUILD_TYPE=Release .
  '';

  installPhase = ''
    mkdir -p $out/bin
    cp my-binary $out/bin/
  '';
}
```

#### Why It’s Declarative:
- The system assumes defaults for all phases (`unpackPhase`, `buildPhase`, `installPhase`), minimizing what you explicitly define.
- Overrides (`configurePhase`, `installPhase`) are declarative: you're stating what you want to achieve, not how to do it imperatively.
- The **output** (`$out`) is central, and the build process revolves around creating a reproducible derivation for it.

---

### **2. Implicit Build Orchestration**
Nix abstracts away the explicit control flow seen in recipes:
- You declare **inputs**, and Nix **derives** the sequence of steps needed to transform those inputs into the desired output.
- Dependencies (`buildInputs`, `nativeBuildInputs`) automatically determine the environment without explicit scripting.

In a traditional recipe, you'd need to **manually orchestrate** each step (e.g., unpack, patch, build, install), but Nix automates these steps unless overridden.

#### **Example: Traditional Recipe vs. Nix**
**Conanfile (Imperative Recipe):**
```python
from conans import ConanFile, CMake

class MyProjectConan(ConanFile):
    name = "my-project"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"
    requires = "fmt/8.0.1"

    def source(self):
        self.run("git clone https://example.com/my-project.git")

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        self.copy("*.h", dst="include", src="src")
        self.copy("*my-binary", dst="bin", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["my-project"]
```

**Nix Derivation (Declarative):**
```nix
{ stdenv, fetchgit, cmake }:

stdenv.mkDerivation {
  name = "my-project";
  version = "1.0";

  src = fetchgit {
    url = "https://example.com/my-project.git";
    rev = "main";
    sha256 = "1abcd...";
  };

  buildInputs = [ cmake ];

  # Optional: Configure overrides
  configurePhase = ''
    cmake -DCMAKE_BUILD_TYPE=Release .
  '';
}
```

- In Nix, no explicit control flow (`self.run`, `cmake.build`, etc.) is required.
- The derivation declaratively states the **inputs** and Nix figures out the build steps.

---

### **3. Hermetic and Reproducible Builds**
Nix makes builds **reproducible** by isolating each phase in its own environment:
- **Dependencies are pinned** (e.g., exact version of `cmake`, compiler).
- **Output paths are deterministic**, derived from inputs and build instructions.

This means that Nix derivations don't execute in the host environment, avoiding the pitfalls of recipes that depend on system state or user intervention.

---

### **4. Separation of Concerns**
In Nix, each **phase** is conceptually isolated:
- You can replace any phase without breaking the rest.
- Dependencies for each phase are declaratively specified, not dynamically fetched at runtime.
  
Recipes like Conan often mix dependency resolution, build logic, and installation steps in a single script. In Nix, these concerns are declaratively separated.

---

### **5. Why This Matters**
The declarative approach allows Nix to:
- **Optimize builds**: Cache and reuse results of identical derivations, even across machines.
- **Enforce reproducibility**: Every derivation is defined entirely by its inputs.
- **Abstract complexity**: You only override phases when absolutely necessary.

In recipes, every action must be explicitly defined and executed in the correct order, leading to potential variability.

---

### **Conclusion**
While Nix's `unpackPhase`, `buildPhase`, and `installPhase` may appear similar to steps in a **recipe**, the key difference is **declarative abstraction**. Nix lets you focus on **what** the environment and output should look like, rather than **how** to execute every step.

If you'd like help creating a custom derivation or transitioning from an imperative recipe to Nix, let me know!