Toggle navigation [](https://platformio.org "PlatformIO")

  * [Get Started ](https://platformio.org/platformio-ide)
    * [What is PlatformIO?](https://docs.platformio.org/en/latest/what-is-platformio.html)
    * [PlatformIO IDE](https://platformio.org/platformio-ide)
    * [PlatformIO Core (CLI)](https://platformio.org/install/cli)
    * [Library Management](https://docs.platformio.org/en/latest/librarymanager/index.html)
    * [Tutorials](https://docs.platformio.org/en/latest/tutorials/index.html)
    * [Project Examples](https://github.com/platformio/platformio-examples)
  * [Solutions ](https://docs.platformio.org/en/latest/plus/pio-remote.html)
    * [PlatformIO IDE](https://platformio.org/platformio-ide)
    * [PlatformIO Core (CLI)](https://platformio.org/install/cli)
    * [Debugging](https://docs.platformio.org/en/latest/plus/debugging.html)
    * [Unit Testing](https://docs.platformio.org/en/latest/advanced/unit-testing/index.html)
    * [Static Code Analysis](https://docs.platformio.org/en/latest/plus/pio-check.html)
    * [Remote Development](https://docs.platformio.org/en/latest/plus/pio-remote.html)
    * [Library Management](https://docs.platformio.org/en/latest/librarymanager/index.html)
    * [Desktop IDEs Integration](https://platformio.org/install/integration)
    * [Cloud IDEs Integration](https://platformio.org/install/integration)
    * [Continuous Integration](https://docs.platformio.org/en/latest/ci/index.html)
  * [Registry](https://registry.platformio.org/)


  * [Docs](https://docs.platformio.org)
  * [Community](https://community.platformio.org/)
  * [Support](https://platformio.org/support)
  * [ TECHNOLOGY](https://piolabs.com/)



[ ](../../../index.html)

  * [What is PlatformIO?](../../../what-is-platformio.html)



Getting Started

  * [PlatformIO IDE](../../../integration/ide/pioide.html)
  * [PlatformIO Core (CLI)](../../../core/index.html)
  * [PlatformIO Home](../../../home/index.html)
  * [PlatformIO Account](../../../plus/pio-account.html)
  * [Tutorials and Examples](../../../tutorials/index.html)



Configuration

  * [platformio.ini](../../../projectconf/index.html)
  * [Build Configurations](../../../projectconf/build_configurations.html)
  * [Environment Variables](../../../envvars.html)



Instruments

  * [Library Management](../../../librarymanager/index.html)
  * [Platforms](../../../platforms/index.html)
  * [Frameworks](../../../frameworks/index.html)
  * [Boards](../../../boards/index.html)
  * [Custom Platform & Board](../../../platforms/custom_platform_and_board.html)



Advanced

  * [Scripting](../../../scripting/index.html)
  * [Debugging](../../../plus/debugging.html)
  * [Unit Testing](../index.html)
    * [Introduction](../introduction.html)
    * [Test Runner](../runner.html)
    * [Project Structure](../structure/index.html)
    * [Configuration](../configuration.html)
    * [Testing Frameworks](index.html)
      * [Doctest](doctest.html)
      * [GoogleTest](#)
        * [Getting Started](#getting-started)
        * [Configuration](#configuration)
        * [GoogleTest CLI](#googletest-cli)
        * [Test Runner](#test-runner)
      * [Unity](unity.html)
      * [Custom](custom/index.html)
    * [Simulators](../simulators/index.html)
    * [Semihosting](../semihosting.html)
    * [CLI Guide](../cli.html)
  * [Static Code Analysis](../../static-code-analysis/index.html)
  * [Remote Development](../../../plus/pio-remote.html)



Integration

  * [Cloud & Desktop IDEs](../../../integration/ide/index.html)
  * [Continuous Integration](../../../integration/ci/index.html)
  * [Compilation database `compile_commands.json`](../../../integration/compile_commands.html)



Miscellaneous

  * [FAQ](../../../faq/index.html)
  * [Release Notes](../../../core/history.html)
  * [Migrating from 5.x to 6.0](../../../core/migration.html)



[PlatformIO](../../../index.html)

  * [](../../../index.html)
  * [Unit Testing](../index.html)
  * [Testing Frameworks](index.html)
  * GoogleTest
  * [ Edit on GitHub](https://github.com/platformio/platformio-docs/blob/develop/advanced/unit-testing/frameworks/googletest.rst)



# GoogleTest[](#googletest "Link to this heading")

Registry:
    

<https://registry.platformio.org/libraries/google/googletest>

Configuration:
    

[test_framework](../../../projectconf/sections/env/options/test/test_framework.html#projectconf-test-framework) = `googletest`

Native Tests:
    

Yes

Embedded Tests:
    

Yes* (only for [Espressif 8266](../../../platforms/espressif8266.html#platform-espressif8266) and [Espressif 32](../../../platforms/espressif32.html#platform-espressif32))

Mocking Support:
    

Yes

**GoogleTest** is a testing framework developed by the Testing Technology team with Google’s specific requirements and constraints in mind. Whether you work on Linux, Windows, or a Mac, if you write C++ code, GoogleTest can help you.

Contents

  * [Getting Started](#getting-started)

  * [Configuration](#configuration)

  * [GoogleTest CLI](#googletest-cli)

  * [Test Runner](#test-runner)




## [Getting Started](#id1)[](#getting-started "Link to this heading")

To get started with the GoogleTest all you need is to set the [test_framework](../../../projectconf/sections/env/options/test/test_framework.html#projectconf-test-framework) option in your [“platformio.ini” (Project Configuration File)](../../../projectconf/index.html#projectconf) to the `googletest` and implement your own `main()` function:

`platformio.ini`

```
[env]
test_framework=googletest
[env:native]
platform=native
[env:esp32dev]
platform=espressif32
framework=arduino
test_framework=googletest

```
Copy to clipboard

`test/test_dummy/test_dummy.cpp`

```
#include<gtest/gtest.h>
// uncomment line below if you plan to use GMock
// #include <gmock/gmock.h>
// TEST(...)
// TEST_F(...)
#if defined(ARDUINO)
#include<Arduino.h>
voidsetup()
{
// should be the same value as for the `test_speed` option in "platformio.ini"
// default value is test_speed=115200
Serial.begin(115200);
::testing::InitGoogleTest();
// if you plan to use GMock, replace the line above with
// ::testing::InitGoogleMock();
}
voidloop()
{
// Run tests
if(RUN_ALL_TESTS())
;
// sleep for 1 sec
delay(1000);
}
#else
intmain(intargc,char**argv)
{
::testing::InitGoogleTest(&argc,argv);
// if you plan to use GMock, replace the line above with
// ::testing::InitGoogleMock(&argc, argv);
if(RUN_ALL_TESTS())
;
// Always return zero-code and allow PlatformIO to parse results
return0;
}
#endif

```
Copy to clipboard

Now, you can run tests using the [pio test](../../../core/userguide/cmd_test.html#cmd-test) command. If you need a full output from the GoogleTest, please use `[pio test --verbose`](../../../core/userguide/cmd_test.html#cmdoption-pio-test-v) option.

**Example**

Please check the complete [GoogleTest example](https://github.com/platformio/platformio-examples/tree/develop/unit-testing/googletest) using GTest, GMock, and PlatformIO.

**Useful links**

  * [GoogleTest Primer](https://google.github.io/googletest/primer.html) - Teaches you how to write simple tests using GoogleTest. Read this first if you are new to GoogleTest

  * [GoogleTest Advanced](https://google.github.io/googletest/advanced.html) - Read this when you’ve finished the Primer and want to utilize GoogleTest to its full potential

  * [GoogleTest Samples](https://google.github.io/googletest/samples.html) - Describes some GoogleTest samples

  * [GoogleTest FAQ](https://google.github.io/googletest/faq.html) - Have a question? Want some tips? Check here first

  * [Mocking for Dummies](https://google.github.io/googletest/gmock_for_dummies.html) - Teaches you how to create mock objects and use them in tests

  * [Mocking Cookbook](https://google.github.io/googletest/gmock_cook_book.html) - Includes tips and approaches to common mocking use cases

  * [Mocking Cheat Sheet](https://google.github.io/googletest/gmock_cheat_sheet.html) - A handy reference for matchers, actions, invariants, and more

  * [Mocking FAQ](https://google.github.io/googletest/gmock_faq.html) - Contains answers to some mocking-specific questions.




## [Configuration](#id2)[](#configuration "Link to this heading")

The GoogleTest can be configured using system environment variables. See supported [GoogleTest environment variables](https://google.github.io/googletest/advanced.html#running-test-programs-advanced-options).

## [GoogleTest CLI](#id3)[](#googletest-cli "Link to this heading")

The GoogleTest works quite nicely without any command-line options at all - but for more control a few of them are available. See [GoogleTest CLI guide](https://google.github.io/googletest/advanced.html#running-test-programs-advanced-options).

There are two options for how to pass extra arguments to the testing program:

  1. Using PlatformIO Core CLI and `[pio test --program-arg`](../../../core/userguide/cmd_test.html#cmdoption-pio-test-a) option

  2. Overriding [test_testing_command](../../../projectconf/sections/env/options/test/test_testing_command.html#projectconf-test-testing-command) with a custom command.




**Example**

Let’s run everything in a test suite `FooTest` except `FooTest.Bar`.

Stop executing test cases after the first error and include successful assertions in the output. We will use the `--gtest_filter` GoogleTest’s CLI option.

  1. Using CLI and `[pio test --program-arg`](../../../core/userguide/cmd_test.html#cmdoption-pio-test-a) option:

```
>piotest--program-arg"--gtest_filter=FooTest.*-FooTest.Bar"
# or short format
>piotest-a"--gtest_filter=FooTest.*-FooTest.Bar"

```
Copy to clipboard

  2. Overriding [test_testing_command](../../../projectconf/sections/env/options/test/test_testing_command.html#projectconf-test-testing-command) with custom command.

```
[env:myenv]
platform=native
test_testing_command=
${platformio.build_dir}/${this.__env__}/program
--gtest_filter=FooTest.*-FooTest.Bar

```
Copy to clipboard




## [Test Runner](#id4)[](#test-runner "Link to this heading")

If you would like to change the default PlatformIO’s Test Runner for the GoogleTest, please implement your [Custom Testing Framework](custom/index.html#unit-testing-frameworks-custom) runner extending [GooglestTestRunner](https://github.com/platformio/platformio-core/blob/develop/platformio/test/runners/googletest.py) class. See [Custom Testing Framework](custom/index.html#unit-testing-frameworks-custom) for examples.

[ Previous](doctest.html "Doctest") [Next ](unity.html "Unity")

© Copyright 2014-present, PlatformIO.

Documentation v6.1.17b2 (latest) 

Versions
    [latest](/en/)
    [stable](/en/stable/)

On Github
    [ View](https://github.com/platformio/platformio-docs/blob/develop/advanced/unit-testing/frameworks/googletest.rst)
    [ Edit](https://github.com/platformio/platformio-docs/edit/develop/advanced/unit-testing/frameworks/googletest.rst)

Search
